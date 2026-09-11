import json, collections, os
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
def dirof(m):
    p=R[m]["path"]
    return os.path.dirname(p)
t=collections.defaultdict(lambda:[0,0])
for m in surv: t[dirof(m)][0 if m in landed else 1]+=1
print(f"{'directory':<70}{'LAND':>5}{'REJ':>5}")
for k,(a,b) in sorted(t.items(), key=lambda kv:-(kv[1][0]+kv[1][1])):
    print(f"{k:<70}{a:>5}{b:>5}  {'MIXED' if a and b else ''}")
