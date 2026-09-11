import json, collections
R=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\agent3\raw_missions.json"))
S=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\mission-acceptance-sets.json"))
landed=set(S['landed']); served=set(S['served'])

def predict(m):
    """Client accepts iff the DA's OWN InternalName FName-equals the name we serve."""
    iname = R[m]["props"].get("InternalName")
    return iname is not None and iname.lower() == m.lower()

TP=FP=FN=TN=0; fp=[]; fn=[]
for m in served:
    p=predict(m); a=(m in landed)
    if p and a: TP+=1
    elif p and not a: FP+=1; fp.append(m)
    elif not p and a: FN+=1; fn.append(m)
    else: TN+=1
print("RULE: accept  <=>  own InternalName exists AND lower(InternalName) == lower(served name)\n")
print("                 predict ACCEPT   predict REJECT")
print(f"actual LANDED   {TP:>10}      {FN:>10}   (126)")
print(f"actual REJECTED {FP:>10}      {TN:>10}   (197)")
print(f"\npredicted accepted total = {TP+FP}   (measured 126)")
print(f"accuracy = {(TP+TN)}/{len(served)} = {100*(TP+TN)/len(served):.2f}%")
print("false positives:", fp)
print("false negatives:", fn)

# reproduce the three required numbers
ABS=lambda m:"CLASS_Abstract" in R[m]["classflags"]
base_with_var=[m for m in served if ABS(m)]
print(f"\ncross-check vs the three mandated numbers:")
variants=[m for m in served if R[m]["parent"]]
bases=[m for m in served if not R[m]["parent"]]
bv=set()
for m in variants:
    p=R[m]["parent"]
    if p in served: bv.add(p)
bnv=[m for m in bases if m not in bv]
print(f"  bases of families WITH variants : {sum(predict(m) for m in bases if m in bv)}/{len([m for m in bases if m in bv])}  (measured 0/75)")
print(f"  bases of families with NO variant: {sum(predict(m) for m in bnv)}/{len(bnv)}  (measured 11/78)")
print(f"  tier variants                    : {sum(predict(m) for m in variants)}/{len(variants)}  (measured 115/218)")
