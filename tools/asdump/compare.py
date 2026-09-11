#!/usr/bin/env python3
r"""Deep, honest comparison of Binds.Cache vs mappings.usmap for /Script/Loki types.
Also drills into the specific 'replicated container type' cases the project has been
burned by (missions / gamestate)."""
import collections, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from binds import parse_binds
from usmap_lite import U

USMAP = r"G:\git\Supervive Revival Project\tools\usmapdump\mappings.usmap"
structs, classes, r, size = parse_binds()
u = U(USMAP)

def mod(p): return p[len("/Script/"):].split(".")[0] if p.startswith("/Script/") else ""
def obj(p): return p.rpartition(".")[2]

DECL = re.compile(r"^(?P<type>.+?)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)$")
def split_decl(decl):
    m = DECL.match(decl.strip())
    return (m.group("type").strip(), m.group("name")) if m else (None, None)

# ---- 1. are the "only in Binds.Cache" props REALLY absent from usmap anywhere?
print("=" * 78)
print("1. Properties Binds.Cache has that usmap's SAME struct lacks")
print("=" * 78)
loki = [(c.type_name, c.unreal_path, c.properties) for c in classes if mod(c.unreal_path) == "Loki"] + \
       [(s.type_name, s.unreal_path, s.properties) for s in structs if mod(s.unreal_path) == "Loki"]
# global index: property name -> set of usmap structs containing it
gidx = collections.defaultdict(set)
for sname, (sup, pc, props) in u.structs.items():
    for _, _, pn, pt in props:
        gidx[pn].add(sname)

missing = []
for tn, up, props in loki:
    un = obj(up)
    if un not in u.structs: continue
    umap = {pn: pt for _, _, pn, pt in u.structs[un][2]}
    for pr in props:
        ty, nm = split_decl(pr.decl)
        if nm and nm not in umap:
            missing.append((un, nm, ty, pr.decl))
print(f"total: {len(missing)}")
tycount = collections.Counter()
for un, nm, ty, decl in missing:
    tycount[(ty or "?").split("<")[0]] += 1
print("by declared type (top 20):")
for k, v in tycount.most_common(20):
    print(f"   {v:>4}  {k}")

# how many are enums?
enumish = [x for x in missing if x[2] and re.match(r"^E[A-Z]", x[2])]
print(f"\nof those, declared type looks like an enum (E<Upper>): {len(enumish)} / {len(missing)}")
print("checking whether the usmap has an *unnamed/renamed* slot for them...")
for un, nm, ty, decl in enumish[:8]:
    sup, pc, props = u.structs[un]
    print(f"   {un}.{nm} ({ty}): usmap struct has propcount={pc}, serialized={len(props)}, "
          f"name present elsewhere in usmap: {sorted(gidx.get(nm, set()))[:3]}")

# ---- 2. deep type comparison including element types
print()
print("=" * 78)
print("2. Element-type agreement on properties present in BOTH")
print("=" * 78)
SCALAR = {"IntProperty": "int", "FloatProperty": "float32", "DoubleProperty": "float64",
          "BoolProperty": "bool", "NameProperty": "FName", "StrProperty": "FString",
          "TextProperty": "FText", "ByteProperty": "uint8", "Int64Property": "int64",
          "UInt32Property": "uint32", "UInt16Property": "uint16", "Int16Property": "int16",
          "Int8Property": "int8", "UInt64Property": "uint64"}

def u_norm(t):
    t = re.sub(r"enum<([A-Za-z0-9_]+):[^>]*>", r"\1", t)
    for k, v in SCALAR.items():
        t = re.sub(rf"\b{k}\b", v, t)
    t = t.replace("Array<", "TArray<").replace("Set<", "TSet<").replace("Map<", "TMap<")
    return re.sub(r"\s+", "", t)

def b_norm(t):
    t = re.sub(r"^const\s+", "", t.strip()).replace("&", "").strip()
    t = t.replace("float", "float32") if t == "float" else t
    return re.sub(r"\s+", "", t)

def container(t):
    m = re.match(r"(TArray|TSet|TMap)<(.*)>$", t)
    return (m.group(1), m.group(2)) if m else (None, t)

agree = disagree = 0
elem_agree = elem_disagree = 0
samples = []
for tn, up, props in loki:
    un = obj(up)
    if un not in u.structs: continue
    umap = {pn: pt for _, _, pn, pt in u.structs[un][2]}
    for pr in props:
        ty, nm = split_decl(pr.decl)
        if not nm or nm not in umap: continue
        a, b = b_norm(ty), u_norm(umap[nm])
        ka, ea = container(a); kb, eb = container(b)
        if ka or kb:
            if ka == kb:
                agree += 1
                # element compare: usmap gives ObjectProperty for any UObject*, so
                # only compare when the usmap element is concrete (F-struct or scalar)
                if eb.startswith("F") or eb in SCALAR.values():
                    if ea.lstrip("F") == eb.lstrip("F"):
                        elem_agree += 1
                    else:
                        elem_disagree += 1
                        if len(samples) < 30:
                            samples.append((un, nm, a, b))
            else:
                disagree += 1
                if len(samples) < 30: samples.append((un, nm, a, b))
print(f"container KIND  agree={agree}  disagree={disagree}")
print(f"container ELEMENT (comparable cases) agree={elem_agree}  disagree={elem_disagree}")
for s in samples[:30]:
    print(f"   DIFF {s[0]}.{s[1]}  binds={s[2]!r}  usmap={s[3]!r}")

# ---- 3. the properties the project actually got burned on
print()
print("=" * 78)
print("3. Drill-down: mission / gamestate replicated containers")
print("=" * 78)
for target in ["LokiGameState", "LokiGameStateBase", "LokiPlayerState_Missions",
               "LokiMissionObjectiveData", "ServerAuthConfig", "LokiPlayerState"]:
    bt = [x for x in loki if obj(x[1]) == target]
    print(f"\n--- {target} ---")
    if not bt:
        print("   (not bound in Binds.Cache)")
    else:
        tn, up, props = bt[0]
        print(f"   Binds.Cache {tn} ({up}) props={len(props)}")
        for pr in props:
            ty, nm = split_decl(pr.decl)
            if ty and re.match(r"T(Array|Set|Map)<", ty):
                un = obj(up)
                uty = None
                if un in u.structs:
                    uty = {pn: pt for _, _, pn, pt in u.structs[un][2]}.get(nm)
                print(f"      {pr.decl:<62} usmap={uty}")
    if target in u.structs:
        sup, pc, props2 = u.structs[target]
        arr = [(pn, pt) for _, _, pn, pt in props2 if pt.startswith(("Array", "Set", "Map"))]
        print(f"   usmap {target}: super={sup} propcount={pc} containers={len(arr)}")
        for pn, pt in arr[:200]:
            print(f"      usmap {pt} {pn}")
