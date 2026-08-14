#!/usr/bin/env python
"""Regenerate the server's offline mission catalog + mission->pool map from the
extracted mission data assets.

    python tools/re/gen_missions_catalog.py

Writes:
    server/internal/interactive/missions_catalog.json   mission -> {pool, objectives[]}
    server/internal/interactive/mission_pools.json      mission -> pool   (subset, kept
                                                        separate because daMissionPool()
                                                        still uses it as an override for
                                                        any non-catalog path)

WHY THIS EXISTS (2026-08-14). FPlayerProgression.MissionInfo is the HTTP door that
populates the client's native mission model (UMissionsModel.Missions), which in turn sets
bAllMissionLoaded and unlocks the lobby banner carousel — with no shim and no .text write.
Building that payload needs a mission list, and the shim-supplied manifest turned out to be
unfit: 75 of its 330 rows have no mission name, several `mission` values are objective
names, its `pool` field is a name-prefix GUESS made inside missions_fix.cpp, and only 23 of
its 122 distinct mission names appear in the data-asset corpus at all.

The data assets carry all of it first-hand. Derivation rules, and what each is grounded in:

  mission name   = DA file name minus "DA_Mission_". That IS the FPrimaryAssetId name —
                   CONFIRMED live: serving "Mission:ArmoryDaily_PlayAGame" made the client
                   resolve the real asset and read XPReward 2500 out of it, matching
                   DA_Mission_ArmoryDaily_PlayAGame.json.
  pool           = Properties.Pool.PrimaryAssetName. Partial coverage is EXPECTED, not a
                   defect: CUE4Parse serializes only NON-DEFAULT properties, so a mission
                   inheriting its pool has no Pool key. Absence means "unknown".
  objective name = Objectives[].ObjectiveClass minus "BP_MissionObjective_" and "_C".
                   BP_MissionObjective_PlayAGame_C -> "PlayAGame", which is exactly what the
                   shim's native GetUniqueObjectiveName() reported for that mission.
                   [!] This rule reproduces only 10 of the manifest's 187 (mission,
                   objective) pairs — mostly because the sources barely overlap (23 missions
                   in common), but it is NOT independently verified at scale. The live
                   discriminator is how many missions the client accepts.
  objective max  = Objectives[].TotalProgress.

XPReward is deliberately NOT emitted: FMissionProgress has no XP field and the client reads
XP from the asset itself (measured).

Re-run after a game patch, AFTER re-extracting the paks.
"""
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DA_GLOB = os.path.join(REPO, "tools", "extractor", "out", "DA_Mission_*.json")
OUT_DIR = os.path.join(REPO, "server", "internal", "interactive")


def objective_name(class_ref: str) -> str:
    """BlueprintGeneratedClass'BP_MissionObjective_PlayAGame_C' -> PlayAGame"""
    n = class_ref.split("'")[1] if "'" in class_ref else class_ref
    n = re.sub(r"_C$", "", n)
    return re.sub(r"^BP_MissionObjective_", "", n)


def main() -> int:
    files = sorted(glob.glob(DA_GLOB))
    if not files:
        print(f"no mission DAs found at {DA_GLOB}", file=sys.stderr)
        print("re-run the extractor first (tools/extractor)", file=sys.stderr)
        return 1

    catalog, pools, skipped, abstract = {}, {}, 0, 0
    for f in files:
        filename = os.path.basename(f)[:-len(".json")][len("DA_Mission_"):]
        try:
            doc = json.load(open(f, encoding="utf-8"))
        except Exception as e:  # a malformed dump must be loud, not silently dropped
            print(f"  ! {os.path.basename(f)}: {e}", file=sys.stderr)
            skipped += 1
            continue

        pool, objectives, debug, internal = None, [], False, None
        for export in doc:
            props = export.get("Properties") or {}
            if props.get("InternalName"):
                internal = props["InternalName"]
            pv = props.get("Pool")
            if isinstance(pv, dict) and pv.get("PrimaryAssetName"):
                pool = pv["PrimaryAssetName"]
            if props.get("IsDebugOnly"):
                debug = True
            for o in props.get("Objectives") or []:
                oc = o.get("ObjectiveClass")
                if isinstance(oc, dict) and oc.get("ObjectName"):
                    objectives.append({
                        "name": objective_name(oc["ObjectName"]),
                        "max": float(o.get("TotalProgress") or 1),
                    })

        # ⚠⚠ THE MISSION NAME IS `InternalName`, NOT THE FILE NAME. This is the whole
        # acceptance rule and it was worth 126 -> 248 missions. The client registers each
        # mission with the AssetManager under the DA's OWN InternalName property; only when
        # that property is absent does it fall back to the asset FName. MEASURED two
        # independent ways (2026-08-14): a live walk of
        # UAssetManager.AssetTypeMap["Mission"].AssetMap (330 entries, keys decoded) and an
        # offline classification of the 323 we were serving (TP=126, FP=0, FN=0).
        # Serving the FILENAME meant 197 of 323 missions named a PrimaryAssetId that does not
        # exist, and the client silently dropped every one.
        # ★ Proof it is a REGISTRY and not per-file equality: the shipped data contains a swap —
        # DA_Mission_Wukong_QKnocks_2 declares InternalName "wukong_qknocks_3" and _3 declares
        # "wukong_qknocks_2". Per-file equality predicts both rejected; both were accepted.
        # ★ Matching is CASE-INSENSITIVE (FName semantics): 41 of the original 126 matched only
        # after case folding, e.g. file Earthtank_RMBAirDunk_3 declares "earthtank_rmbairdunk_3".
        # No InternalName => a CLASS_Abstract base template. MEASURED: exactly 75 such DAs, all
        # with exactly 1 objective and all in the HunterMissions pool. They ARE registered with the
        # AssetManager, but under their FULL asset FName *including* the DA_Mission_ prefix
        # (live registered keys minus the InternalName set = 75 entries, all prefixed —
        # 'da_mission_alchemist_healwithq' etc). That is precisely why stripping the prefix made
        # all 75 unresolvable, and it is the mechanism behind the old
        # "bases of a variant-family never land: 0/75" observation.
        # So they are servable — just under the prefixed key.
        is_abstract = internal is None
        name = internal if internal is not None else "DA_Mission_" + filename
        if is_abstract:
            abstract += 1

        if not objectives:
            # No objective => nothing the progress store can key on. Counted, not hidden.
            skipped += 1
            continue

        entry = {"objectives": objectives}
        if is_abstract:
            # Marked so the server (and a reader) can tell a template apart from a real
            # mission. Served under its prefixed registered key; see the note above.
            entry["abstract"] = True
        if pool:
            entry["pool"] = pool
            pools[name] = pool
        if debug:
            entry["debug"] = True
        catalog[name] = entry

    cat_path = os.path.join(OUT_DIR, "missions_catalog.json")
    pool_path = os.path.join(OUT_DIR, "mission_pools.json")
    json.dump(catalog, open(cat_path, "w", encoding="utf-8"), indent=0, sort_keys=True)
    json.dump(pools, open(pool_path, "w", encoding="utf-8"), indent=1, sort_keys=True)

    print(f"DA files scanned      : {len(files)}")
    print(f"abstract (CLASS_Abstract, served under DA_Mission_ prefix): {abstract}")
    print(f"missions written      : {len(catalog)}")
    print(f"  with a declared pool: {len(pools)}")
    print(f"  IsDebugOnly         : {sum(1 for v in catalog.values() if v.get('debug'))}")
    print(f"objectives written    : {sum(len(v['objectives']) for v in catalog.values())}")
    print(f"skipped (no objective or unreadable): {skipped}")
    diff = sum(1 for n in catalog if n not in {os.path.basename(f)[:-5][len("DA_Mission_"):] for f in files})
    print(f"names differing from their filename  : {diff}  <- these were ALL being dropped before")
    print(f"-> {cat_path}")
    print(f"-> {pool_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
