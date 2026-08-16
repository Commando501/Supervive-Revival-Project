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

print("abstract x cookrule (landed/total):")
t=collections.defaultdict(lambda:[0,0])
for m in served: t[(ABS(m),CR(m))][0 if m in landed else 1]+=1
for k,(a,b) in sorted(t.items()): print(f"  abstract={k[0]!s:<5} cook={k[1]:<12} landed={a:>4} rej={b:>4} tot={a+b:>4}")

surv=[m for m in served if not ABS(m) and CR(m)!="Never"]
print(f"\nAfter removing abstract OR CookRule::Never: {len(surv)} remain, "
      f"{len([m for m in surv if m in landed])} landed, {len([m for m in surv if m not in landed])} rejected")
missed=[m for m in served if (ABS(m) or CR(m)=='Never') and m in landed]
print("landed but abstract-or-Never (should be 0):", missed)

# what remains rejected?
rem=sorted(m for m in surv if m not in landed)
print(f"\nremaining rejected ({len(rem)}):")
for m in rem: print("   ",m)
