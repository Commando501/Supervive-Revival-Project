import sys, os, collections
sys.path.insert(0, os.path.join(os.getcwd(),'scratchpad','s131','tools'))
import rectab
for k,v in [('merged4','merged4.dump.exe'),('merged3','merged3.dump.exe')]:
    rectab.P[k]=os.path.join(os.getcwd(),'dumps',v)
rectab.P['rideable']=os.path.join(os.getcwd(),'dumps','s131-rideable-live','SUPERVIVE-Win64-Shipping.dump.exe')
recs=rectab.scan('merged4')
idx=collections.defaultdict(list)
for r in recs: idx[r['name']].append(r)
NAMES=["AuthAddPlayer","AuthPlayerDetachPlayerFromRidable","AuthPlayerEnterWorld",
 "AuthPlayerEnterWorldAttachedToRidable","AuthPlayerEnterWorldNew","AuthPlayerPreSpawnOnAddToPlane",
 "AuthRemovePlayer","AuthSetCanJump","CanExit","ContainsPlayer","GetLandingTeleportLocation",
 "GetRidePosition","HasEverContainedPlayer","MulticastOnPlayerEntered","MulticastOnPlayerEnteredWorld",
 "MulticastOnPlayerExited","SpawnDropPodForTeam","AuthBeginGlideDiveFromDropPod","AddPlayerToPlane",
 "AddPlayerToDropPlane","SpawnPlane","OverridePlaneLocations","AuthSetSpawnTeamLeader","SetDropLeader",
 "SpawnPlayer","GoToPhase","AuthSetCurrentPhase"]
# fold-page-coverage check uses merged4 only
def cov(irv, dumps):
    hit=[]
    for dn in dumps:
        data,base,secs=rectab.L(dn)
        pg=irv & ~0xFFF
        if any(data[pg:pg+0x1000]): hit.append(dn)
    return hit
DUMPS=('merged4','merged3','tuthero','s129','rideable')
print(f"{'name':<40} {'thunk':>9} {'impl':>9}  grade")
for n in NAMES:
    rs=idx.get(n,[])
    if not rs:
        print(f"{n:<40} {'-':>9} {'-':>9}  NO RECORD (not a registered UFunction name in .data table)")
        continue
    seen=set()
    for r in rs:
        k=(r['thunk'],r['impl'])
        if k in seen: continue
        seen.add(k)
        f=rectab.FOLD.get(r['impl'])
        if f: g=f"EMPTY ({f})"
        else:
            c=cov(r['impl'],DUMPS)
            if not c: g="COVERAGE-BLOCKED (impl page all-zero in 5/5 images)"
            else:
                data,base,secs=rectab.L(c[0]); g=f"REAL  bytes={data[r['impl']:r['impl']+10].hex()}  [{','.join(c)}]"
        print(f"{n:<40} 0x{r['thunk']:07X} 0x{r['impl']:07X}  {g}")
