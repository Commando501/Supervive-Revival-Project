import json, collections
R=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\agent3\raw_missions.json"))
S=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\mission-acceptance-sets.json"))
landed=set(S['landed']); served=set(S['served'])
def eff(name,key):
    n=name;d=0
    while n and d<10:
        p=R[n]["props"]
        if key in p: return p[key]
        n=R[n]["parent"];d+=1
    return None
ABS=lambda m:"CLASS_Abstract" in R[m]["classflags"]
CR =lambda m:(eff(m,"CookRule") or "").split("::")[-1]
surv=[m for m in served if not ABS(m) and CR(m)!="Never"]
def hero(m):
    h=eff(m,"Hero")
    return h.get("PrimaryAssetName") if h else "<none>"
t=collections.defaultdict(lambda:[0,0])
for m in surv: t[hero(m)][0 if m in landed else 1]+=1
print(f"{'Hero':<22}{'LAND':>6}{'REJ':>6}{'tot':>6}")
for k,(a,b) in sorted(t.items(), key=lambda kv:(-(kv[1][0]+kv[1][1]),kv[0])):
    print(f"{k:<22}{a:>6}{b:>6}{a+b:>6}   {'MIXED' if a and b else ''}")
