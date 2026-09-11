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
for m in surv: fam[R[m]["parent"] or ("ROOT:"+m)].append(m)
allin=allout=mixed=0
mixedfams=[]
for k,v in sorted(fam.items()):
    L=[x for x in v if x in landed]
    if len(L)==len(v): allin+=1
    elif not L: allout+=1
    else: mixed+=1; mixedfams.append((k,sorted(L),sorted(set(v)-set(L))))
print(f"families among survivors: {len(fam)}  all-landed={allin}  all-rejected={allout}  MIXED={mixed}")
for k,L,Rj in mixedfams: print("  MIXED",k,"landed",L,"rej",Rj)
