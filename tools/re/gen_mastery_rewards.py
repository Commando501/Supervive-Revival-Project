#!/usr/bin/env python
"""Regenerate the server's hero-mastery reward catalog from the extracted mastery data assets.

    python tools/re/gen_mastery_rewards.py

Writes:
    server/internal/interactive/mastery_rewards.json    hero InternalName -> {level -> "Type:Name"}

WHY THIS EXISTS (2026-08-14, S120). FPlayerProgression.HeroMastery[].UnclaimedRewards is a
TMap<int32, FHeroMasteryRewardClaimData{ClaimID FString; SKU FPrimaryAssetId}> — the backend field
that tells the client which mastery levels have an unclaimed reward waiting. To serve it we need,
per hero, the reward each level grants. The game ships exactly that as LevelRewards on each
LokiDataAsset_HeroMastery, so the catalog is derived from the assets rather than invented.

MEASURED over the 25 shipped mastery DAs (tools/extractor/out/*Mastery_uasset.json):
  - all 25 declare exactly 7 LevelRewards, keys "0".."6" — no hero deviates;
  - the value is an FPrimaryAssetId; the four types used are
    Emote / SlotCosmetics / HeroCosmeticsBundle / PlayerTitle;
  - InternalName == Hero.PrimaryAssetName on all 25, which is why one key serves both the
    HeroMastery entry's HeroId ("Hero:<name>") and this table.

⚠ THE KEY DOMAIN DOES NOT RECONCILE CLEANLY AND IS NOT SETTLED [I]. There are 7 LevelRewards
(0..6), 8 MasteryLevelProgression.XPAmounts, and WBP_HeroMastery_LevelIcon clamps Level to [0,8]
(9 slots) — and the live per-hero BattlepassViewModel carries Levels Num=9 (MEASURED). So "reward
key == mastery level index" is the natural reading but is NOT proven; a level above 6 simply has no
reward here. Do not record it as measured, and do not synthesise a reward for a level the asset
does not declare.

Re-run after a game patch, AFTER re-extracting the paks.
"""
import glob
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DA_GLOB = os.path.join(REPO, "tools", "extractor", "out", "*Mastery_uasset.json")
OUT_DIR = os.path.join(REPO, "server", "internal", "interactive")

# LevelRewards serialises as an ordered list of {"Key": "<n>", "Value": {PrimaryAssetType/Name}}.
PAIR = re.compile(
    r'"Key":\s*"(\d+)"\s*,\s*"Value":\s*\{\s*'
    r'"PrimaryAssetType":\s*\{\s*"Name":\s*"([^"]+)"\s*\}\s*,\s*'
    r'"PrimaryAssetName":\s*"([^"]+)"'
)


def main() -> int:
    files = sorted(glob.glob(DA_GLOB))
    if not files:
        print(f"no mastery DAs found at {DA_GLOB}", file=sys.stderr)
        print("re-run the extractor first (tools/extractor)", file=sys.stderr)
        return 1

    out, skipped = {}, 0
    for f in files:
        text = open(f, encoding="utf-8").read()
        m = re.search(r'"InternalName":\s*"([^"]+)"', text)
        if not m:
            # Every shipped mastery DA declares one; a miss means the corpus changed.
            print(f"  ! {os.path.basename(f)}: no InternalName", file=sys.stderr)
            skipped += 1
            continue
        hero = m.group(1)

        # Scope the scan to the LevelRewards block. The asset also contains other
        # Key/Value maps, and a whole-file scan would silently absorb them.
        i = text.find('"LevelRewards"')
        if i < 0:
            print(f"  ! {hero}: no LevelRewards", file=sys.stderr)
            skipped += 1
            continue
        j = text.find('"LevelClass"', i)
        block = text[i:j if j > i else len(text)]

        rewards = {k: f"{t}:{n}" for k, t, n in PAIR.findall(block)}
        if not rewards:
            print(f"  ! {hero}: LevelRewards parsed empty", file=sys.stderr)
            skipped += 1
            continue
        out[hero] = rewards

    path = os.path.join(OUT_DIR, "mastery_rewards.json")
    json.dump(out, open(path, "w", encoding="utf-8"), indent=0, sort_keys=True)

    counts = sorted({len(v) for v in out.values()})
    types = sorted({v.split(":", 1)[0] for r in out.values() for v in r.values()})
    print(f"mastery DAs scanned : {len(files)}")
    print(f"heroes written      : {len(out)}")
    print(f"rewards per hero    : {counts}   (expect [7])")
    print(f"total rewards       : {sum(len(v) for v in out.values())}")
    print(f"reward types        : {', '.join(types)}")
    print(f"skipped             : {skipped}")
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
