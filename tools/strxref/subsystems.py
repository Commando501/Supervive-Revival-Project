#!/usr/bin/env python3
"""
subsystems.py -- lit/dark rate per named subsystem.

"48.6% of UTF-16 strings are unreferenced" is not actionable.  "97% of the ability-
system strings are unreferenced but 71% of the menu ones are lit" is: it says which
runtime state would decrypt the code we cannot currently see.

Method: each subsystem is a list of case-insensitive substrings that only occur in that
subsystem's messages.  For every indexed string matching any of them, is it LIT
(>=1 code xref) or DARK (0)?  A string is counted once, for the first family it matches,
and the families are ordered most-specific-first.  Raw counts are printed so the reader
can see how much each rate rests on.
"""
import os
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strxref as SX

IDX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index", "strxref.idx")

FAMILIES = [
    ("ability / GAS", ["GameplayAbility", "AbilitySystem", "GameplayEffect", "GameplayCue",
                       "GameplayTag", "AttributeSet", "AbilityTask", "GameplayAbilitySpec"]),
    ("char movement / CMC", ["CharacterMovement", "ServerMove", "ClientAdjustPosition",
                             "RootMotion", "MoveAutonomous", "NetworkPrediction",
                             "ClientAckGoodMove", "MovementMode"]),
    ("replication / netcode", ["ActorChannel", "PackageMapClient", "RepLayout",
                               "NetConnection", "NetDriver", "ReplicationReader",
                               "ReplicationWriter", "ReplicationFiltering", "NetGUID",
                               "NetworkObjectList", "PropertyChannel", "Bunch"]),
    ("party beacon / matchmaking", ["PartyBeacon", "OnlineBeacon", "Matchmaking",
                                    "SessionInterface", "FindSession", "JoinSession"]),
    ("replay / demo", ["ReplayStreamer", "DemoNetDriver", "ReplayHelper", "DemoRewind"]),
    ("Loki gameplay (game-specific)", ["LokiCharacter", "LokiPlayerState", "LokiGameMode",
                                       "LokiGameState", "LokiAbility", "LokiHero",
                                       "LokiCombat", "LokiDamage", "LokiPawn",
                                       "LokiPlayerController", "LokiWeapon"]),
    ("Loki menu / frontend", ["LokiCatalog", "LokiStore", "LokiInventory", "LokiParty",
                              "LokiProgression", "Battlepass", "LokiLobby", "ViewModel",
                              "PersonalizationLoadout", "MissionModel"]),
    ("drop / deploy", ["DropPlane", "DropPod", "SpawnPlane", "Deploy", "Breach",
                       "MatchTransition"]),
    ("navigation / AI", ["NavMesh", "dtNavMesh", "NavigationData", "Recast", "BehaviorTree",
                         "AIController", "Blackboard", "PathFollowing"]),
    ("physics / collision", ["Chaos", "PhysicsAsset", "CollisionQuery", "BodyInstance",
                             "PhysScene", "RigidBody"]),
    ("animation", ["AnimInstance", "AnimMontage", "AnimBlueprint", "SkeletalMesh",
                   "AnimNode", "AnimGraph", "BoneContainer"]),
    ("audio / Wwise", ["Wwise", "AkComponent", "AkAudio", "SoundCue", "AudioDevice",
                       "AudioComponent"]),
    ("renderer", ["HairStrands", "Nanite", "Lumen", "PathTracing", "Substrate",
                  "ShadowSetup", "SceneVisibility", "RenderGraph", "PostProcess",
                  "ShaderPrint"]),
    ("UI / Slate / UMG", ["SWidget", "UMG", "UserWidget", "SlateApplication",
                          "WidgetTree", "CommonUI"]),
    ("asset / IoStore / cooking", ["IoStore", "IoDispatcher", "AssetRegistry",
                                   "PrimaryAsset", "LinkerLoad", "PackageName",
                                   "StreamableManager"]),
]


def main():
    idx = SX.Index.load(IDX)
    d = idx._dump()
    n = len(idx.s_rva)
    ref = [0] * n
    for si in idx.rs_str:
        ref[si] += 1

    pat = [(name, [k.lower() for k in keys]) for name, keys in FAMILIES]
    stat = collections.OrderedDict((nm, [0, 0]) for nm, _ in pat)
    ex = collections.defaultdict(list)

    for i in range(n):
        s = idx.text_of(i, d).lower()
        for nm, keys in pat:
            if any(k in s for k in keys):
                stat[nm][0 if ref[i] else 1] += 1
                if not ref[i] and len(ex[nm]) < 4:
                    ex[nm].append(idx.text_of(i, d)[:78])
                break

    print(f"{'subsystem':<32} {'lit':>7} {'dark':>7} {'total':>7} {'lit%':>7}")
    print("-" * 66)
    rows = []
    for nm in stat:
        lit, dark = stat[nm]
        t = lit + dark
        if t == 0:
            continue
        rows.append((100.0 * lit / t, nm, lit, dark, t))
    for r, nm, lit, dark, t in sorted(rows):
        print(f"{nm:<32} {lit:7d} {dark:7d} {t:7d} {r:6.1f}%")

    print("\nsample DARK strings from the least-covered families:")
    for r, nm, lit, dark, t in sorted(rows)[:7]:
        print(f"\n  [{nm}]  ({r:.1f}% lit)")
        for s in ex[nm]:
            print(f"    {s!r}")


if __name__ == "__main__":
    main()
