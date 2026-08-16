import json, collections
R=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\agent3\raw_missions.json"))
S=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\mission-acceptance-sets.json"))
landed=set(S['landed']); served=set(S['served'])
def eff(n,k):
    d=0
    while n and d<10:
        if k in R[n]["props"]: return R[n]["props"][k]
        n=R[n]["parent"];d+=1
    return None
ABS=lambda m:"CLASS_Abstract" in R[m]["classflags"]
CR =lambda m:(eff(m,"CookRule") or "").split("::")[-1]
surv=[m for m in served if not ABS(m) and CR(m)!="Never"]
def sv(m):
    v=eff(m,"ShippingVersion")
    return (v or {}).get("VersionName","<absent>") if v is not None else "<absent>"
t=collections.defaultdict(lambda:[0,0])
for m in surv: t[sv(m)][0 if m in landed else 1]+=1
print("=== ShippingVersion (survivors, mission level) ===")
for k,(a,b) in sorted(t.items()):
    print(f"  {k:<16} land={a:>4} rej={b:>4}  {'MIXED' if a and b else ('ALL-LAND' if a else 'ALL-REJ')}")
# also on the whole served set
t2=collections.defaultdict(lambda:[0,0])
for m in served: t2[sv(m)][0 if m in landed else 1]+=1
print("\n=== ShippingVersion (ALL 323 served) ===")
for k,(a,b) in sorted(t2.items()):
    print(f"  {k:<16} land={a:>4} rej={b:>4}")
