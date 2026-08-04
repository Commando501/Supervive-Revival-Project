#!/usr/bin/env python3
r"""Dump the NATIVE (C++) bind surface that the drop-phase Angelscript modules
sit on top of.  The script layer (LokiDropPod / LokiDropShip / LokiDropPodLaser /
LokiDropPodImpactIndicator / LokiDropPhase_PlayerStateComponent) is only the LEAF
of the drop sequence: the phase driver, the plane, the pod base class and the
player drop-plane component are all C++.  Their declarations ARE recorded in
Binds.Cache, so this prints them verbatim.

usage:  python dropphase_binds.py [substring ...]
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asdump

SCRIPT_DIR = r"G:\git\GAME BACKUPS FOR REVERSE ENGINEERING\SUPERVIVE\Loki\Script"

TYPES = [
    "ALokiDropPlane", "ALokiDropPodBase", "ULokiPlayerDropPlaneComponent",
    "ULokiRideableComponent", "ALokiHeightMap", "ALokiDropPod",
    "FGameEvent_OnDropPodStateChanged_PlayerState",
    "FGameEvent_CrewDropPodDetach_PlayerState",
    "FGameEvent_LeaderDropPodDetach_PlayerState",
    "FGameEvent_PodMoveDirectionChanged_PlayerState",
    "FGameEvent_PodSteeringEnabled",
    "FGameEvent_GameAugmentSet",
    "ALokiGameAugment",
]


def dump_type(b, t):
    rec = b.by_type.get(t)
    print("=" * 78)
    if not rec:
        print("%-50s  NOT IN Binds.Cache" % t)
        return
    kind = "struct" if t in b.struct_names else "class"
    print("%s %s" % (kind, t))
    print("  unreal : %s" % rec["path"])
    hdr = b.headers.get(rec["path"])
    if hdr:
        print("  header : %s" % hdr)
    if rec["props"]:
        print("  -- properties (%d) --" % len(rec["props"]))
        for p in rec["props"]:
            flags = "".join(c for c, on in
                            (("r", p["can_read"]), ("w", p["can_write"]), ("e", p["can_edit"])) if on)
            alias = ""
            if p["name"] and p["name"] != asdump.as_decl_name(p["decl"], True):
                alias = "   [UProperty %s]" % p["name"]
            print("     %-6s %s%s" % ("(%s)" % flags, p["decl"], alias))
    if rec.get("methods"):
        print("  -- methods (%d) --" % len(rec["methods"]))
        for m in rec["methods"]:
            nm = m["script_name"] or asdump.as_decl_name(m["decl"])
            extra = []
            if m["ufunc"] and m["ufunc"] != nm:
                extra.append("UFunction=%s" % m["ufunc"])
            if m["static_unreal"]:
                extra.append("staticUE")
            if m["static_script"]:
                extra.append("staticAS")
            if m["global_scope"]:
                extra.append("global")
            if m["world_ctx"] >= 0:
                extra.append("worldctx@%d" % m["world_ctx"])
            print("     %s%s" % (m["decl"], ("   ; " + ", ".join(extra)) if extra else ""))


def grep_methods(b, needles):
    print("=" * 78)
    print("GLOBAL / FREE FUNCTIONS matching: %s" % ", ".join(needles))
    seen = set()
    for c in b.classes:
        for m in c["methods"]:
            nm = m["script_name"] or asdump.as_decl_name(m["decl"])
            d = m["decl"]
            if any(n.lower() in (nm or "").lower() or n.lower() in d.lower() for n in needles):
                key = (c["type"], d)
                if key in seen:
                    continue
                seen.add(key)
                scope = "global " if m["global_scope"] else ""
                print("   [%s] %s%s" % (c["type"], scope, d))


if __name__ == "__main__":
    b = asdump.load_binds(os.path.join(SCRIPT_DIR, "Binds.Cache"),
                          os.path.join(SCRIPT_DIR, "Binds.Cache.Headers"))
    args = sys.argv[1:]
    if args:
        for a in args:
            hits = [t for t in b.by_type if a.lower() in t.lower()]
            for t in sorted(hits):
                dump_type(b, t)
    else:
        for t in TYPES:
            dump_type(b, t)
