import json, collections
R=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\agent3\raw_missions.json"))
S=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\mission-acceptance-sets.json"))
landed=set(S['landed']); served=set(S['served'])
noname=[n for n,v in R.items() if v["props"].get("InternalName") is None]
print(f"DAs with NO own InternalName: {len(noname)}")
print("  ...all parentless (true base)?    ", all(R[n]['parent'] is None for n in noname))
print("  ...all CLASS_Abstract?            ", all('CLASS_Abstract' in R[n]['classflags'] for n in noname))
abst=[n for n in R if 'CLASS_Abstract' in R[n]['classflags']]
print(f"  CLASS_Abstract count: {len(abst)}   identical set: {set(abst)==set(noname)}")
print("  any VARIANT lacking own InternalName?", [n for n in noname if R[n]['parent']])

# do any DAs declare an InternalName not equal (case-insens) to their filename?
mis=[(n,R[n]['props']['InternalName']) for n in R if R[n]['props'].get('InternalName') and R[n]['props']['InternalName'].lower()!=n.lower()]
print(f"\nDAs whose InternalName != own filename (case-insens): {len(mis)}")
served_by_other=[ (n,i) for n,i in mis if i.lower() in {m.lower() for m in served} ]
print(f"  ...of which the InternalName IS a served name (the swap cases): {served_by_other}")

# the 11 no-variant bases that land
REG={v['props']['InternalName'].lower() for n,v in R.items() if v['props'].get('InternalName')}
bases=[m for m in served if not R[m]['parent']]
bv={R[m]['parent'] for m in served if R[m]['parent'] in served}
bnv=[m for m in bases if m not in bv]
print(f"\nbases={len(bases)}  of-a-family-with-variants={len(bv)}  no-variant-bases={len(bnv)}  ({len(bv)}+{len(bnv)}={len(bv)+len(bnv)})")
print("no-variant bases that LAND:", sorted(m for m in bnv if m.lower() in REG))
print("no-variant bases that DON'T:", sorted(m for m in bnv if m.lower() not in REG))
# base-less families (only _N present)
import re
fams=collections.defaultdict(list)
for m in served:
    p=R[m]['parent']; fams[p or m].append(m)
print(f"\nfamilies (by Template parent) = {len(fams)}; base-less (parent not served) = "
      f"{len([k for k in fams if k not in served])}")
