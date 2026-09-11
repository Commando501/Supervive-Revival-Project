import json, collections
R=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\agent3\raw_missions.json"))
S=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\mission-acceptance-sets.json"))
landed=set(S['landed']); served=set(S['served'])

# The client's registry of PrimaryAssetName: every DA that declares its OWN InternalName.
# FName comparison is case-insensitive -> fold case.
REGISTRY = {}
for n,v in R.items():
    i=v["props"].get("InternalName")
    if i is not None: REGISTRY.setdefault(i.lower(), []).append(n)
print(f"registry size = {len(REGISTRY)} distinct InternalNames from {len(R)} DA files")
dups={k:v for k,v in REGISTRY.items() if len(v)>1}
print("duplicate InternalNames:", dups)
noname=[n for n,v in R.items() if v["props"].get("InternalName") is None]
print(f"DAs with NO own InternalName: {len(noname)}")

predict=lambda m: m.lower() in REGISTRY

TP=FP=FN=TN=0; fp=[]; fn=[]
for m in served:
    p=predict(m); a=(m in landed)
    if   p and a: TP+=1
    elif p and not a: FP+=1; fp.append(m)
    elif a: FN+=1; fn.append(m)
    else: TN+=1
print("\n" + "="*74)
print("RULE: the client accepts a served mission iff its PrimaryAssetName matches,")
print("      case-insensitively, the InternalName declared by some cooked Mission DA.")
print("="*74)
print("                    predict ACCEPT   predict REJECT     total")
print(f"actual LANDED   {TP:>14}   {FN:>14}   {TP+FN:>9}")
print(f"actual REJECTED {FP:>14}   {TN:>14}   {FP+TN:>9}")
print(f"\nPREDICTED ACCEPTED = {TP+FP}      MEASURED = {len(landed)}")
print(f"accuracy = {TP+TN}/{len(served)} = {100*(TP+TN)/len(served):.2f}%   FP={FP}  FN={FN}")
print("false positives:", fp or "none")
print("false negatives:", fn or "none")

# mandated cross-checks
variants=[m for m in served if R[m]["parent"]]
bases=[m for m in served if not R[m]["parent"]]
bv={R[m]["parent"] for m in variants if R[m]["parent"] in served}
bnv=[m for m in bases if m not in bv]
bwv=[m for m in bases if m in bv]
print(f"\nmandated cross-checks:")
print(f"  bases of families WITH variants  : {sum(predict(m) for m in bwv):>3}/{len(bwv):<3} (measured   0/75)")
print(f"  bases of families with NO variant: {sum(predict(m) for m in bnv):>3}/{len(bnv):<3} (measured  11/78)")
print(f"  tier variants                    : {sum(predict(m) for m in variants):>3}/{len(variants):<3} (measured 115/218)")

# NEGATIVE CONTROL: a rule that must fail - "accept iff CookRule==Production"
def eff(n,k):
    d=0
    while n and d<10:
        if k in R[n]["props"]: return R[n]["props"][k]
        n=R[n]["parent"];d+=1
    return None
ctrl=lambda m:(eff(m,"CookRule") or "").endswith("Production")
c=sum(1 for m in served if ctrl(m)==(m in landed))
print(f"\n[NEG CONTROL] 'CookRule==Production' rule: {c}/{len(served)} = {100*c/len(served):.1f}%  (must be well under 100%)")
# POSITIVE CONTROL: identity oracle must score 100%
c2=sum(1 for m in served if (m in landed)==(m in landed))
print(f"[POS CONTROL] identity oracle: {c2}/{len(served)} = 100.0%  (must be 100%)")

json.dump({"registry_lower":sorted(REGISTRY), "predicted_accept":sorted(m for m in served if predict(m)),
           "no_internalname_das":sorted(noname)},
          open(r"G:\git\Supervive Revival Project\scratchpad\agent3\rule_result.json","w"), indent=1)
