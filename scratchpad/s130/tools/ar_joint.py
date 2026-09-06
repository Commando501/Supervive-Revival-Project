#!/usr/bin/env python
"""Joint distribution of (bEnablePooling, bCanEverReplicate) over every Blueprint
in the cooked AssetRegistry.

WHY: C7 in the pooled acquire is `if (CDO->byte@0x6C != 0) return NULL`, and
AActor+0x6C is bCanEverReplicate [M].  If that reading is right, then NO class
with bCanEverReplicate=true can ever be pooled-spawned.  So the joint
distribution is a hard test of the reading:

  * if {pooling=True, replicate=false} is a large coherent set  -> C7 is a real
    design gate and the drop pod simply fails it;
  * if almost every pooled class has replicate=true             -> C7 as read
    would make pooling universally dead, which is a far stronger claim than the
    evidence supports, and the reading needs to be re-examined.

The control that motivated this: BP_GemV2 is pooled (LokiGem.as sets
bEnablePooling=true; the log shows it registered) AND has bCanEverReplicate=true.
"""
import json, io, collections, argparse

AR = r"G:\git\Supervive Revival Project\tools\extractor\out\assetregistry_candidates_Blueprint.json"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default=None, help="print asset names for this 'pool,repl' cell")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()

    data = json.load(io.open(AR, encoding="utf-8"))
    joint = collections.Counter()
    cells = collections.defaultdict(list)
    for e in data:
        t = e.get("Tags") or {}
        if "bEnablePooling" not in t and "bCanEverReplicate" not in t:
            continue
        p = str(t.get("bEnablePooling", "<absent>")).lower()
        r = str(t.get("bCanEverReplicate", "<absent>")).lower()
        joint[(p, r)] += 1
        cells[(p, r)].append(e.get("AssetName"))

    total = sum(joint.values())
    print("Blueprints carrying at least one of the two tags: %d of %d (unit: assets)" % (total, len(data)))
    print("\n  bEnablePooling | bCanEverReplicate |  count")
    print("  ---------------+-------------------+-------")
    for (p, r), n in sorted(joint.items(), key=lambda kv: -kv[1]):
        print("  %-14s | %-17s | %6d" % (p, r, n))

    if a.show:
        p, r = a.show.split(",")
        key = (p.strip().lower(), r.strip().lower())
        names = cells.get(key, [])
        print("\ncell %s -> %d assets; first %d:" % (key, len(names), a.limit))
        for n in names[:a.limit]:
            print("   ", n)
