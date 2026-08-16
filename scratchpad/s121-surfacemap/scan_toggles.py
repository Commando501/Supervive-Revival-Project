#!/usr/bin/env python3
"""S121 — enumerate every WBP_UI_ClientConfigVisbilityToggleWidget_C INSTANCE in the
extracted catalog, with its FeatureKey / ConfigKey / IsEnabledByDefault and the widget
it wraps (NamedSlotBindings -> Content), plus its parent slot.

OFFLINE ONLY. Reads tools/extractor/out/**.json. Writes nothing outside scratchpad.

⚠ INSTRUMENT NOTE: serialized property keys carry a [N] suffix (e.g. "FeatureKey[2]"),
so an exact-match grep for '"FeatureKey"' finds only the class asset itself (1 file).
Match by prefix.
"""
import json, os, re, sys, collections

ROOT = r"G:\git\Supervive Revival Project\tools\extractor\out"
TOGGLE = "WBP_UI_ClientConfigVisbilityToggleWidget_C"

def propget(props, name):
    """Return value of props[name] or props['name[N]']."""
    if name in props:
        return props[name]
    for k, v in props.items():
        if k == name or (k.startswith(name + "[") and k.endswith("]")):
            return v
    return None

def objname(ref):
    if not isinstance(ref, dict):
        return None
    on = ref.get("ObjectName")
    if not on:
        return None
    # Type'Path:Outer.Name'  -> keep class + leaf
    m = re.match(r"^([^']+)'(.*)'$", on)
    if m:
        cls, path = m.group(1), m.group(2)
        leaf = path.split(".")[-1]
        return f"{leaf} <{cls}>"
    return on

rows = []
noKeyInstances = []
files_scanned = 0
files_with_toggle = 0

for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith(".json"):
            continue
        p = os.path.join(dp, f)
        try:
            with open(p, "rb") as fh:
                blob = fh.read()
        except Exception:
            continue
        files_scanned += 1
        if TOGGLE.encode() not in blob:
            continue
        try:
            d = json.loads(blob.decode("utf-8", "replace"))
        except Exception as e:
            print(f"PARSE FAIL {p}: {e}", file=sys.stderr)
            continue
        if not isinstance(d, list):
            continue
        # index every export by name for slot lookups
        byname = {}
        for o in d:
            if isinstance(o, dict) and o.get("Name"):
                byname.setdefault(o["Name"], []).append(o)
        found_here = False
        for o in d:
            if not isinstance(o, dict):
                continue
            if o.get("Type") != TOGGLE:
                continue
            # skip the CDO of the toggle asset itself
            if str(o.get("Name", "")).startswith("Default__"):
                continue
            found_here = True
            props = o.get("Properties", {}) or {}
            fk = propget(props, "FeatureKey")
            ck = propget(props, "ConfigKey")
            dflt = propget(props, "IsEnabledByDefault")
            nsb = propget(props, "NamedSlotBindings") or []
            wrapped = []
            for b in nsb:
                c = b.get("Content")
                wrapped.append(f"{b.get('Name')}={objname(c)}")
            slot = objname(propget(props, "Slot"))
            rec = dict(asset=os.path.basename(p)[:-5], instance=o.get("Name"),
                       featureKey=fk, configKey=ck, isEnabledByDefault=dflt,
                       wraps="; ".join(wrapped) if wrapped else None, slot=slot,
                       allprops=sorted(props.keys()))
            rows.append(rec)
            if fk is None:
                noKeyInstances.append(rec)
        if found_here:
            files_with_toggle += 1

print(f"files scanned      : {files_scanned}")
print(f"files with toggle  : {files_with_toggle}")
print(f"toggle INSTANCES   : {len(rows)}")
keys = [r["featureKey"] for r in rows if r["featureKey"] is not None]
print(f"instances w/ FeatureKey override : {len(keys)}")
print(f"instances w/o FeatureKey (CDO default) : {len(noKeyInstances)}")
print(f"DISTINCT FeatureKeys : {len(set(keys))}")
ck = [r["configKey"] for r in rows if r["configKey"] is not None]
print(f"instances w/ ConfigKey override : {len(ck)}  distinct={sorted(set(ck))}")
dt = [r for r in rows if r["isEnabledByDefault"] is True]
print(f"instances with IsEnabledByDefault==TRUE : {len(dt)}")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "toggle_instances.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1)
print("wrote", out)

# per-key summary
bykey = collections.defaultdict(list)
for r in rows:
    bykey[r["featureKey"]].append(r)
print("\n=== per-key ===")
for k in sorted(bykey, key=lambda x: (x is None, str(x).lower())):
    rs = bykey[k]
    defaults = collections.Counter(str(r["isEnabledByDefault"]) for r in rs)
    print(f"{k!r:42} sites={len(rs):3}  defaults={dict(defaults)}  assets={sorted(set(r['asset'] for r in rs))}")
