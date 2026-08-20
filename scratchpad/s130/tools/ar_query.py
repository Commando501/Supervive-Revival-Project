#!/usr/bin/env python
"""Query the extracted AssetRegistry for per-asset cooked tag values.

`bEnablePooling` is CPF_AssetRegistrySearchable on AActor, so the cooker writes
its EFFECTIVE (inherited-or-overridden) value into every Blueprint's registry
tags.  That makes the registry the one offline source for "what does class X
actually end up with", as opposed to "what did the .uasset serialize as a delta".

Usage:
  ar_query.py --name BP_DropPod_Tutorial            # dump one asset's tags
  ar_query.py --tag bCanEverReplicate               # distribution of a tag value
  ar_query.py --tag bEnablePooling --value True     # who has it
"""
import json, argparse, collections, io

AR = r"G:\git\Supervive Revival Project\tools\extractor\out\assetregistry_candidates_Blueprint.json"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--value", default=None)
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    data = json.load(io.open(AR, encoding="utf-8"))
    print("assets in registry: %d (unit: Blueprint assets)" % len(data))

    if a.name:
        hits = [e for e in data if a.name.lower() in (e.get("AssetName") or "").lower()]
        print("matches for %r: %d" % (a.name, len(hits)))
        for e in hits[:a.limit]:
            print("\n== %s  (%s)" % (e.get("AssetName"), e.get("PackageName")))
            tags = e.get("Tags") or {}
            for k in sorted(tags):
                v = tags[k]
                if isinstance(v, str) and len(v) > 90:
                    v = v[:90] + "... (%d chars, likely base64)" % len(tags[k])
                print("   %-34s = %s" % (k, v))

    if a.tag:
        dist = collections.Counter()
        who = []
        for e in data:
            tags = e.get("Tags") or {}
            if a.tag in tags:
                dist[str(tags[a.tag])] += 1
                if a.value is None or str(tags[a.tag]) == a.value:
                    who.append((e.get("AssetName"), str(tags[a.tag])))
        print("\nassets carrying tag %r: %d" % (a.tag, sum(dist.values())))
        for v, n in dist.most_common():
            print("   value %-10s : %d" % (v, n))
        if a.value is not None:
            print("\nassets with %s == %s (first %d of %d):" % (a.tag, a.value, a.limit, len(who)))
            for n, v in who[:a.limit]:
                print("   ", n)
