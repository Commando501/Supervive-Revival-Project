import json, collections
R=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\agent3\raw_missions.json"))
S=json.load(open(r"G:\git\Supervive Revival Project\scratchpad\mission-acceptance-sets.json"))
landed=set(S['landed']); served=set(S['served']); rejected=set(S['rejected'])

def eff(name, key):
    """effective value walking up Template chain; returns (value, 'own'|'inh'|'absent')"""
    n=name; depth=0
    while n and depth<10:
        p=R[n]["props"]
        if key in p: return p[key], ("own" if n==name else "inh")
        n=R[n]["parent"]; depth+=1
    return None,"absent"

def xtab(label, fn, universe=served):
    tab=collections.defaultdict(lambda:[0,0])
    for m in universe:
        v=fn(m)
        tab[v][0 if m in landed else 1]+=1
    print(f"\n=== {label} ===")
    print(f"{'value':<60} {'LANDED':>7} {'REJ':>7} {'tot':>6}  {'%':>5}")
    for v,(a,b) in sorted(tab.items(), key=lambda kv:-(kv[1][0]+kv[1][1])):
        print(f"{str(v):<60} {a:>7} {b:>7} {a+b:>6}  {100*a/(a+b):>5.1f}")

# 1. CookRule (own only)
xtab("CookRule OWN (present key only)", lambda m: R[m]["props"].get("CookRule","<ABSENT>"))
# 2. CookRule effective
xtab("CookRule EFFECTIVE (inherited)", lambda m: str(eff(m,"CookRule")))
# 3. ClassFlags
xtab("ClassFlags", lambda m: R[m]["classflags"])
xtab("CLASS_Abstract present", lambda m: "CLASS_Abstract" in R[m]["classflags"])
