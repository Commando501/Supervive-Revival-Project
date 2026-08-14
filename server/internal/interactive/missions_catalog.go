package interactive

import (
	_ "embed"
	"encoding/json"
	"log"
	"sort"
)

// CatalogMission is one mission as its own data asset declares it.
type CatalogMission struct {
	Pool  string `json:"pool,omitempty"`
	Debug bool   `json:"debug,omitempty"`
	// Abstract marks a CLASS_Abstract base template (75 of 323). These declare no
	// InternalName, so they are registered with the AssetManager under their FULL asset
	// FName *including* the DA_Mission_ prefix — which is why the catalog key for them is
	// "DA_Mission_<file>" while every other mission is keyed by its InternalName. They are
	// tier-0 bases of the hero-mission families, all with exactly one objective and all in
	// the HunterMissions pool. Kept as a distinct flag so a template is never mistaken for
	// an authored mission when reading the catalog or debugging a render.
	Abstract   bool               `json:"abstract,omitempty"`
	Objectives []CatalogObjective `json:"objectives"`
}

// CatalogObjective is one objective: the unique name the progress store keys on, and the
// TotalProgress the data asset declares as its completion target.
type CatalogObjective struct {
	Name string  `json:"name"`
	Max  float64 `json:"max"`
}

// missions_catalog.json is the mission catalog, built OFFLINE from the 323 extracted
// DA_Mission_*.json that declare at least one objective. It replaces the shim-supplied
// manifest as the source for FMissionInfo.
//
// WHY THE MANIFEST WAS DROPPED (2026-08-14). missions_fix POSTs /revival/missions/manifest
// and we used to build MissionData from it. MEASURED, and it is not fit for the purpose:
//
//   - 75 of its 330 rows carry NO mission name at all;
//   - several `mission` values are plainly OBJECTIVE names (wukong_shiftempowereddamage,
//     VoidVoidSnapIntoKill, Void_BlackholeMultiples), not missions;
//   - its `pool` field is a NAME-PREFIX GUESS made inside the shim
//     (missions_fix.cpp:188-192), not data read from the game — it files
//     Armory_WeeklyWinGame under "ArmoryOnboarding" when that mission's own data asset
//     declares "WeeklyChallenges", and ArmoryDaily_GetKnocks under "DailyChallenge" when
//     its asset says "Daily";
//   - only 23 of its 122 distinct mission names appear in the DA corpus at all.
//
// The data assets carry all of it first-hand, so the catalog is derived from them:
//
//	mission name  = the DA's file name minus the "DA_Mission_" prefix. That IS the
//	                FPrimaryAssetId name — CONFIRMED live: we served
//	                "Mission:ArmoryDaily_PlayAGame" and the client resolved it to the real
//	                asset and read XPReward 2500 out of it, matching
//	                DA_Mission_ArmoryDaily_PlayAGame.json exactly.
//	pool          = Properties.Pool.PrimaryAssetName (105 of 323; see mission_pools.go on
//	                why partial coverage is expected rather than a defect).
//	objective name= Objectives[].ObjectiveClass minus the "BP_MissionObjective_" prefix and
//	                the "_C" suffix. The shim got this from a native
//	                GetUniqueObjectiveName() call; the class name reproduces it —
//	                BP_MissionObjective_PlayAGame_C -> "PlayAGame", which is exactly what
//	                the shim reported for that mission.
//	objective max = Objectives[].TotalProgress (1.0 for PlayAGame, matching the shim's max=1).
//
// ⚠ HONEST LIMIT: the objective-name rule reproduces only 10 of the manifest's 187
// (mission, objective) pairs. That is mostly because the two sources barely overlap — 23
// missions in common — but it does mean the rule is NOT independently verified at scale.
// The live discriminator is how many missions the client accepts; that is the test this
// catalog exists to run, and it is why the previous behaviour is still one revert away.
//
// XPReward is deliberately NOT served: FMissionProgress has no XP field, and the client
// reads XP from the data asset itself (measured — UMissionModel.XPReward came back 2500
// without us sending it).
//
// Regenerate after a game patch (re-extract the paks first) with the script in
// tools/re/gen_missions_catalog.py.
//
//go:embed missions_catalog.json
var missionsCatalogJSON []byte

// missionCatalog is mission FPrimaryAssetId name -> its declared pool and objectives.
var missionCatalog = func() map[string]CatalogMission {
	m := map[string]CatalogMission{}
	if err := json.Unmarshal(missionsCatalogJSON, &m); err != nil {
		// Loud: an unreadable catalog means MissionInfo silently serves nothing, which
		// would look exactly like the native mission load being broken again.
		log.Printf("missions: missions_catalog.json failed to parse (%v) — MissionInfo will be empty", err)
		return map[string]CatalogMission{}
	}
	return m
}()

// catalogMissionNames returns the catalog's mission names in a stable (sorted) order, so
// the served document — and therefore its content digest — does not churn between requests.
func catalogMissionNames() []string {
	names := make([]string, 0, len(missionCatalog))
	for n := range missionCatalog {
		names = append(names, n)
	}
	sort.Strings(names)
	return names
}
