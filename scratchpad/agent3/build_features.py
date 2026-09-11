import json, os, glob, collections, sys

OUT = r"G:\git\Supervive Revival Project\tools\extractor\out"
sets = json.load(open(r"G:\git\Supervive Revival Project\scratchpad\mission-acceptance-sets.json"))
landed=set(sets['landed']); served=set(sets['served']); rejected=set(sets['rejected'])

files = glob.glob(os.path.join(OUT,"DA_Mission_*.json"))
print("DA_Mission_* files:", len(files))

recs={}
for f in files:
    name = os.path.basename(f)[len("DA_Mission_"):-len(".json")]
    try:
        j=json.load(open(f,encoding='utf-8'))
    except Exception as e:
        print("PARSE FAIL", name, e); continue
    bgc=None; cdo=None
    for o in j:
        if o.get("Type")=="BlueprintGeneratedClass": bgc=o
        elif o.get("Name","").startswith("Default__"): cdo=o
    recs[name]={"file":f,"bgc":bgc,"cdo":cdo,"props":(cdo or {}).get("Properties",{}) or {}}

print("parsed:", len(recs))
print("served not in recs:", sorted(served-set(recs))[:20])
print("recs not served:", sorted(set(recs)-served))

# ---- parent resolution via Template / Super objectname ----
def parent_of(name):
    r=recs[name]
    cdo=r["cdo"] or {}
    t=cdo.get("Template")
    if t:
        on=t.get("ObjectName","")  # DA_Mission_X_C'Default__DA_Mission_X_C'
        if "Default__DA_Mission_" in on:
            p=on.split("Default__DA_Mission_")[1].rstrip("'")
            if p.endswith("_C"): p=p[:-2]
            return p
    b=r["bgc"] or {}
    s=b.get("Super")
    if s:
        on=s.get("ObjectName","")
        if "DA_Mission_" in on:
            p=on.split("DA_Mission_")[1].rstrip("'")
            if p.endswith("_C"): p=p[:-2]
            return p
    return None

parents={n:parent_of(n) for n in recs}
nparent=sum(1 for v in parents.values() if v)
print("with parent:", nparent, " orphan parents:", sorted({v for v in parents.values() if v and v not in recs}))

json.dump({n:{"parent":parents[n],"props":recs[n]["props"],
              "classflags":(recs[n]["bgc"] or {}).get("ClassFlags",""),
              "flags":(recs[n]["cdo"] or {}).get("Flags",""),
              "path":((recs[n]["bgc"] or {}).get("ClassDefaultObject",{}) or {}).get("ObjectPath","")}
           for n in recs}, open(r"G:\git\Supervive Revival Project\scratchpad\agent3\raw_missions.json","w"), indent=0)
print("wrote raw_missions.json")
