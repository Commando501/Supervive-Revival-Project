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
def own(m,k): return R[m]["props"].get(k)

# 2x2: InternalName OWN present?  and does it equal the filename?
def cat(m):
    o=own(m,"InternalName"); e=eff(m,"InternalName")
    if o is None and e is None: return "no InternalName anywhere"
    if o is None: return "inherited from parent (=%s)" % ("parentname" if e==R[m]["parent"] else "other")
    return "own, ==filename" if o==m else "own, !=filename(%s)"%o
t=collections.defaultdict(lambda:[0,0])
for m in served: t[cat(m)][0 if m in landed else 1]+=1
print("=== InternalName category (all 323) ===")
for k,(a,b) in sorted(t.items(), key=lambda kv:-(kv[1][0]+kv[1][1])):
    print(f"  {k:<45} land={a:>4} rej={b:>4}")

# simple 2x2: own InternalName present at all
t=collections.defaultdict(lambda:[0,0])
for m in served: t[own(m,"InternalName") is not None][0 if m in landed else 1]+=1
print("\n=== OWN InternalName present? (all 323) ===")
for k,(a,b) in sorted(t.items()): print(f"  {k!s:<8} land={a:>4} rej={b:>4}  tot={a+b}")
