#!/usr/bin/env python3
r"""Analysis pass over Binds.Cache: Loki subsystem census + honest comparison of
Binds.Cache vs the project's mappings.usmap as a schema source."""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from binds import parse_binds, parse_headers
from usmap_lite import U

USMAP = r"G:\git\Supervive Revival Project\tools\usmapdump\mappings.usmap"

structs, classes, r, size = parse_binds()
pairs, hr, hsz = parse_headers()

def mod(p):
    return p[len("/Script/"):].split(".")[0] if p.startswith("/Script/") else "(none)"

def obj(p):
    return p.rpartition(".")[2]

loki_c = [c for c in classes if mod(c.unreal_path) == "Loki"]
loki_s = [s for s in structs if mod(s.unreal_path) == "Loki"]

print("=" * 78)
print("A. /Script/Loki SUBSYSTEM CENSUS")
print("=" * 78)
print(f"classes={len(loki_c)} structs={len(loki_s)} "
      f"methods={sum(len(c.methods) for c in loki_c)} "
      f"class-props={sum(len(c.properties) for c in loki_c)} "
      f"struct-props={sum(len(s.properties) for s in loki_s)}")

KEYS = ["Drop", "Barracuda", "FFA", "Respawn", "Minion", "Creep", "Tower", "Airship",
        "Vault", "MostWanted", "Domination", "Tutorial", "Training", "Cheat",
        "GameFeature", "Party", "Hero", "Ability", "Catalog", "Progression", "Mission",
        "Battlepass", "Pass", "Loadout", "Cosmetic", "Shop", "Item", "Bot", "Spectat",
        "Replay", "Objective", "Structure", "Lane", "Jungle", "Camp", "Wave"]
print("\nLoki type-name keyword census (class+struct):")
allnames = [(c.type_name, c.unreal_path, "class") for c in loki_c] + \
           [(s.type_name, s.unreal_path, "struct") for s in loki_s]
for k in KEYS:
    hits = [n for n, p, kind in allnames if k.lower() in n.lower()]
    if hits:
        print(f"  {k:<12} {len(hits):>4}  e.g. {', '.join(sorted(hits)[:6])}")

print("\n--- DROP-PHASE bound types (the 'DROP IN GEAR UP LOADING' wall) ---")
for n, p, kind in sorted(allnames):
    if "drop" in n.lower():
        print(f"   {kind:<6} {n:<52} {p}")

print("\n--- DROP-PHASE bound METHODS ---")
for c in loki_c:
    if "drop" in c.type_name.lower():
        for m in c.methods:
            print(f"   {c.type_name}::{m.unreal_path:<34} {m.decl}")

print("\n--- FFA / respawn bound methods ---")
for c in loki_c:
    if re.search(r"FFA|Respawn", c.type_name, re.I):
        print(f"   [{c.type_name}]  {c.unreal_path}")
        for m in c.methods:
            print(f"       {m.decl}")

print("\n--- Barracuda bound types ---")
for n, p, kind in sorted(allnames):
    if "barracuda" in n.lower():
        print(f"   {kind:<6} {n:<52} {p}")

print("\n--- LokiPlayerCheats bound surface ---")
for c in loki_c:
    if "cheat" in c.type_name.lower():
        print(f"   [{c.type_name}] {c.unreal_path}  methods={len(c.methods)}")
        for m in c.methods[:200]:
            print(f"       {m.decl}")

# ------------------------------------------------------------------ usmap compare
print()
print("=" * 78)
print("B. Binds.Cache vs mappings.usmap  (schema-source comparison)")
print("=" * 78)
u = U(USMAP)
print(f"usmap: names={len(u.names):,} enums={len(u.enums):,} structs={len(u.structs):,}")

DECL = re.compile(r"^(?P<type>.+?)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)$")

def as_type_of(decl):
    m = DECL.match(decl.strip())
    return (m.group("type").strip(), m.group("name")) if m else (None, None)

def norm_as(t):
    t = t.strip()
    t = re.sub(r"^const\s+", "", t).replace("&", "").strip()
    t = t.replace("TArray<", "Array<").replace("TSet<", "Set<").replace("TMap<", "Map<")
    t = re.sub(r"\s+", "", t)
    return t

def norm_usmap(t):
    t = t.strip()
    repl = {"IntProperty": "int32", "FloatProperty": "float32", "DoubleProperty": "float64",
            "BoolProperty": "bool", "NameProperty": "FName", "StrProperty": "FString",
            "TextProperty": "FText", "ByteProperty": "uint8", "Int64Property": "int64",
            "UInt32Property": "uint32", "UInt16Property": "uint16", "Int16Property": "int16",
            "Int8Property": "int8", "UInt64Property": "uint64",
            "ObjectProperty": "OBJ", "WeakObjectProperty": "OBJ", "SoftObjectProperty": "OBJ",
            "LazyObjectProperty": "OBJ", "AssetObjectProperty": "OBJ",
            "InterfaceProperty": "OBJ", "ClassProperty": "OBJ",
            "MulticastDelegateProperty": "DELEGATE", "DelegateProperty": "DELEGATE",
            "FieldPathProperty": "FIELDPATH"}
    for k, v in repl.items():
        t = t.replace(k, v)
    t = re.sub(r"enum<([^:]+):[^>]*>", r"\1", t)
    return re.sub(r"\s+", "", t)

both = missing_type = 0
prop_in_both = prop_only_binds = prop_only_usmap = 0
container_match = container_mismatch = 0
mismatch_samples = []
onlybinds_samples = []
cov = []

for lst, kind in ((loki_c, "class"), (loki_s, "struct")):
    for t in lst:
        un = obj(t.unreal_path)
        if un not in u.structs:
            missing_type += 1
            continue
        both += 1
        _, _, uprops = u.structs[un]
        umap = {pn: pt for _, _, pn, pt in uprops}
        bnames = set()
        for pr in t.properties:
            ty, nm = as_type_of(pr.decl)
            if nm is None:
                continue
            bnames.add(nm)
            if nm in umap:
                prop_in_both += 1
                a, b = norm_as(ty), norm_usmap(umap[nm])
                ac = re.match(r"(Array|Set|Map)<", a)
                bc = re.match(r"(Array|Set|Map)<", b)
                if (ac is not None) == (bc is not None):
                    if ac and ac.group(1) == bc.group(1):
                        container_match += 1
                    elif ac:
                        container_mismatch += 1
                        if len(mismatch_samples) < 25:
                            mismatch_samples.append((un, nm, a, b))
                else:
                    container_mismatch += 1
                    if len(mismatch_samples) < 25:
                        mismatch_samples.append((un, nm, a, b))
            else:
                prop_only_binds += 1
                if len(onlybinds_samples) < 15:
                    onlybinds_samples.append((un, nm, ty))
        only_u = set(umap) - bnames
        prop_only_usmap += len(only_u)
        if umap:
            cov.append(len(bnames & set(umap)) / len(umap))

print(f"\nLoki bound types present in usmap: {both}   absent from usmap: {missing_type}")
print(f"properties in BOTH: {prop_in_both:,}")
print(f"properties only in Binds.Cache (usmap lacks them): {prop_only_binds:,}")
print(f"properties only in usmap (Binds.Cache lacks them): {prop_only_usmap:,}")
if cov:
    print(f"mean per-type coverage of usmap props by Binds.Cache: {sum(cov)/len(cov):.1%}")
print(f"\ncontainer-shape AGREE: {container_match:,}   DISAGREE: {container_mismatch:,}")
for s in mismatch_samples:
    print(f"   MISMATCH {s[0]}.{s[1]}:  binds={s[2]!r}  usmap={s[3]!r}")
print("\nproperties Binds.Cache has that usmap does NOT (sample):")
for s in onlybinds_samples:
    print(f"   {s[0]}.{s[1]} : {s[2]}")

# headers value
print()
print("=" * 78)
print("C. Binds.Cache.Headers value")
print("=" * 78)
roots = collections.Counter()
for up, hp in pairs:
    h = hp.replace("/", "\\")
    parts = h.split("\\")
    roots["\\".join(parts[:4])] += 1
for k, v in roots.most_common(12):
    print(f"   {v:>6}  {k}")
lok = [(u_, h) for u_, h in pairs if u_.startswith("/Script/Loki.")]
print(f"\n/Script/Loki.* header entries: {len(lok)}")
for u_, h in lok[:12]:
    print(f"   {u_:<52} {h}")
