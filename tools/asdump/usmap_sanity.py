#!/usr/bin/env python3
r"""Decide: are the usmap's container INNER types garbage, or is our reader wrong?
Test against engine types whose real UE 5.4 definition is public knowledge."""
import collections, os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from usmap_lite import U
from binds import parse_binds

MAPS = [r"G:\git\Supervive Revival Project\tools\usmapdump\mappings.usmap",
        r"G:\git\Supervive Revival Project\mappings.usmap"]

# (struct, prop) -> real UE5.4 type, from engine headers (ground truth, independent of both files)
KNOWN = [
    ("Actor", "Tags",                       "Array<NameProperty>"),
    ("Actor", "InstanceComponents",         "Array<ObjectProperty>"),
    ("Actor", "BlueprintCreatedComponents", "Array<ObjectProperty>"),
    ("ARFilter", "PackageNames",            "Array<NameProperty>"),
    ("ARFilter", "PackagePaths",            "Array<NameProperty>"),
    ("ARFilter", "ClassNames",              "Array<NameProperty>"),
    ("ActorComponent", "ComponentTags",     "Array<NameProperty>"),
    ("GameModeBase", "GameSession",         "ObjectProperty"),
    ("PlayerState", "PlayerNamePrivate",    "StrProperty"),
    ("Pawn", "Controller",                  "ObjectProperty"),
    ("Character", "Mesh",                   "ObjectProperty"),
    ("GameStateBase", "PlayerArray",        "Array<ObjectProperty>"),
    ("SceneComponent", "AttachChildren",    "Array<ObjectProperty>"),
    ("Level", "Actors",                     "Array<ObjectProperty>"),
    ("BlueprintGeneratedClass", "Timelines","Array<ObjectProperty>"),
]

for path in MAPS:
    if not os.path.exists(path):
        continue
    print("=" * 78)
    print(path)
    print("=" * 78)
    u = U(path)
    print(f"names={len(u.names):,} enums={len(u.enums):,} structs={len(u.structs):,} "
          f"unconsumed={u.remaining}")
    ok = bad = absent = 0
    for st, pn, expect in KNOWN:
        if st not in u.structs:
            print(f"   ABSENT struct {st}"); absent += 1; continue
        got = {n: t for _, _, n, t in u.structs[st][2]}.get(pn)
        if got is None:
            print(f"   ABSENT prop  {st}.{pn}"); absent += 1; continue
        mark = "OK  " if got == expect else "WRONG"
        if got == expect: ok += 1
        else: bad += 1
        print(f"   {mark} {st}.{pn:<26} usmap={got!r}   real={expect!r}")
    print(f"   => known-truth check: ok={ok} wrong={bad} absent={absent}")

    # distribution of inner types across ALL array properties in the whole usmap
    inner = collections.Counter()
    outer = collections.Counter()
    for sn, (sup, pc, props) in u.structs.items():
        for _, _, pn, pt in props:
            m = re.match(r"(Array|Set)<(.+)>$", pt)
            if m:
                outer[m.group(1)] += 1
                inner[m.group(2).split("<")[0]] += 1
    print(f"\n   container props: {sum(outer.values()):,}  inner-type distribution:")
    for k, v in inner.most_common(14):
        print(f"      {v:>6}  {k}")
    print()
