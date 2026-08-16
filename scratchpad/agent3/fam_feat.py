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
fam=collections.defaultdict(list)
for m in surv: fam[R[m]["parent"] or m].append(m)
famlab={k:(1 if v[0] in landed else 0) for k,v in fam.items()}

# every effective key seen anywhere on a representative member
keys=set()
for k,v in fam.items():
    n=v[0]
    while n:
        keys.update(R[n]["props"].keys()); n=R[n]["parent"]
def score(fn,label):
    t=collections.defaultdict(lambda:[0,0])
    for k,v in fam.items(): t[fn(k,v)][famlab[k]]+=1
    # purity: how many families are in a pure bucket
    pure=sum(max(a,b) for a,b in t.values()); tot=sum(a+b for a,b in t.values())
    return pure/tot, t
res=[]
for key in sorted(keys):
    for mode,fn in (("presence",lambda k,v,key=key: eff(v[0],key) is not None),
                    ("value",   lambda k,v,key=key: json.dumps(eff(v[0],key),sort_keys=True)[:80])):
        p,t=score(fn,key)
        res.append((p,key,mode,t))
res.sort(reverse=True)
print("family-level separators (105 families: 51 landed / 54 rejected)\n")
for p,key,mode,t in res[:18]:
    print(f"purity {p*100:5.1f}%  {key} [{mode}]  buckets={len(t)}")
    if len(t)<=8:
        for val,(rj,ld) in sorted(t.items(), key=lambda kv:-(kv[1][0]+kv[1][1])):
            print(f"      {str(val)[:70]:<72} land={ld:>3} rej={rj:>3}")
