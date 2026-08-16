import json, csv, collections
R=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\agent3\raw_missions.json"))
S=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\mission-acceptance-sets.json"))
landed=set(S['landed']); served=set(S['served'])
def eff(n,k):
    d=0
    while n and d<10:
        if k in R[n]["props"]: return R[n]["props"][k]
        n=R[n]["parent"];d+=1
    return None
REG={v['props']['InternalName'].lower():n for n,v in R.items() if v['props'].get('InternalName')}
rows=[]
for m in sorted(R):
    p=R[m]["props"]; iname=p.get("InternalName")
    h=eff(m,"Hero") or {}
    rows.append(dict(
        name=m, served=m in served, landed=m in landed,
        predict_land=m.lower() in REG,
        internal_name=iname or "", has_own_internalname=iname is not None,
        iname_eq_filename_ci=(iname or "").lower()==m.lower(),
        registry_owner=REG.get(m.lower(),""),
        class_abstract="CLASS_Abstract" in R[m]["classflags"],
        parent=R[m]["parent"] or "",
        cookrule_eff=(eff(m,"CookRule") or "").split("::")[-1],
        shipping_version=(eff(m,"ShippingVersion") or {}).get("VersionName",""),
        pool_eff=(eff(m,"Pool") or {}).get("PrimaryAssetName",""),
        hero=h.get("PrimaryAssetName",""),
        xp=eff(m,"XPReward"),
        n_objectives=len(eff(m,"Objectives") or []),
        path=R[m]["path"]))
with open(r"G:\git\Supervive Revival Project\scratchpad\agent3\mission_feature_table.csv","w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print("wrote mission_feature_table.csv  rows=",len(rows))

sw=[m for m in served if R[m]["props"].get("InternalName")]
print(f"\nserved DAs that declare an InternalName: {len(sw)}")
inames={R[m]['props']['InternalName'] for m in sw}
print(f"distinct InternalNames among them: {len(inames)}  (collision-free: {len(inames)==len(sw)})")
print(f"=> if the backend served AssetId = Mission:<InternalName>, predicted landed = {len(sw)}  (vs 126 today)")
newly=sorted(m for m in sw if m not in landed)
print(f"newly landing missions: {len(newly)}")
# sanity: self-matching count
selfm=[n for n in R if (R[n]['props'].get('InternalName') or '').lower()==n.lower()]
print(f"\narithmetic check: self-matching DAs={len(selfm)}, of which served={len([n for n in selfm if n in served])}, "
      f"+2 Wukong swap targets = {len([n for n in selfm if n in served])+2} == 126")
