package interactive

import (
	_ "embed"
	"encoding/json"
	"log"
)

// mission_pools.json maps a mission's FPrimaryAssetId NAME to the pool NAME its own data
// asset declares, e.g. "ArmoryDaily_PlayAGame" -> "DailyChallenge".
//
// WHY IT EXISTS (2026-08-14). Until now the pool served in FMissionInfo came from the
// manifest that missions_fix POSTs, and that field is a NAME-PREFIX GUESS made inside the
// shim, not data read from the game. From tools/sigbypass-mod/missions_fix.cpp:188-192:
//
//	if      (startsWith(n,"Tournament"))                        pj = FindPoolSub("Tournament");
//	else if (startsWith(n,"ArmoryDaily"))                       pj = FindPoolSub("DailyChallenge");
//	else if (startsWith(n,"ArmoryOnboarding")||startsWith(n,"Armory"))
//	                                                            pj = FindPoolSub("ArmoryOnboarding");
//	...
//	else                                                        pj = FindPoolSub("Hunter");
//
// MEASURED to be wrong: DA_Mission_Armory_WeeklyWinGame declares
// `Pool = MissionPool:WeeklyChallenges`, but the prefix rule files it under
// "ArmoryOnboarding". DA_Mission_ArmoryDaily_GetKnocks declares "Daily", not
// "DailyChallenge". The same guesswork is why handlePutMission carried
// "MissionPool:DA_MissionPoolDailyEasy" for a mission whose pool is DailyChallenge.
//
// GROUND TRUTH is each mission data asset's own `Pool` property (an FPrimaryAssetId whose
// PrimaryAssetName is the pool id). This file is generated from the 330 extracted
// DA_Mission_*.json under tools/extractor/out by reading Properties.Pool.PrimaryAssetName.
//
// ⚠ COVERAGE IS PARTIAL AND THAT IS EXPECTED, NOT A BUG: 105 of 330. CUE4Parse serializes
// only NON-DEFAULT properties, so a mission that inherits its pool from a parent class
// simply has no Pool key in the dump. Absence here therefore means "unknown", never
// "no pool" — which is exactly why daMissionPool falls back rather than overriding with "".
//
// Regenerate after a game patch (re-extract first), from the repo root:
//
//	python -c "import json,glob,os; out={};
//	[out.update({os.path.basename(f)[:-5][len('DA_Mission_'):]: (e.get('Properties') or {})['Pool']['PrimaryAssetName']})
//	 for f in glob.glob('tools/extractor/out/DA_Mission_*.json')
//	 for e in json.load(open(f,encoding='utf-8'))
//	 if isinstance((e.get('Properties') or {}).get('Pool'), dict)];
//	json.dump(out, open('server/internal/interactive/mission_pools.json','w'), indent=1, sort_keys=True)"
//
//go:embed mission_pools.json
var missionPoolsJSON []byte

var missionPools = func() map[string]string {
	m := map[string]string{}
	if err := json.Unmarshal(missionPoolsJSON, &m); err != nil {
		// Not fatal: an unreadable map degrades to the manifest's guess, which is what
		// we served before this file existed. Loud, because it silently changes data.
		log.Printf("missions: mission_pools.json failed to parse (%v) — falling back to manifest pools", err)
		return map[string]string{}
	}
	return m
}()

// daMissionPool returns the pool the mission's DATA ASSET declares, falling back to the
// manifest's guessed pool when the asset dump did not carry one. Never returns "" when a
// fallback is available.
func daMissionPool(mission, manifestPool string) string {
	if p := missionPools[mission]; p != "" {
		return p
	}
	return manifestPool
}
