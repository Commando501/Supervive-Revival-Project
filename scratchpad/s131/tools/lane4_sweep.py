# S131 LANE 4 -- .data record sweep over FK-22 2.5's drop-class (class,func) keys.
# Read-only, offline, over cold PE dumps. Re-runnable from repo root:
#     python scratchpad/s131/tools/lane4_sweep.py
import sys, os, csv, collections, struct
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
import rectab
ROOT=rectab.ROOT
UHT=os.path.join(ROOT,'tools','re','out','uht_funcflags_tuthero.csv')

DROP_CLASSES=['ALokiDropPlane','ULokiPlayerDropPlaneComponent','ULokiRideableComponent',
              'ALokiTeamState_TeamOnly','ALokiDropPodBase','ULokiGameModeDropPlaneComponent',
              'ULokiDropPhaseLibrary','ULokiRideableInterface']
EXTRA=[('ALokiGameMode','SpawnPlayer'),('ALokiPlayerState','AuthSetSpawnTeamLeader'),
       ('ULokiCharacterMovementComponent','AuthBeginGlideDiveFromDropPod'),
       ('ULokiCharacterMovementComponent','AuthBeginGlideDive'),
       ('ULokiCharacterMovementComponent','EndGlideDive'),
       ('ALokiServerAnalyticsManager','AddTeamDropEvent')]
GOLD_EMPTY=[('ALokiGameMode','SpawnPlayer',0xF7EB50),('ALokiPlayerState','AuthSetSpawnTeamLeader',0xF7EC20),
            ('ALokiTeamState_TeamOnly','SetDropLeader',0xF7EC20),('ALokiDropPlane','OverridePlaneLocations',0xF7EC20)]
GOLD_REAL=[('ALokiRoundGameMode','GoToPhase',0x5601020),('ALokiGameState','BP_AuthSetCurrentPhase',0x567A160),
           ('ALokiRoundGameMode','OnNewPhase',0x330C56C)]

def load_uht():
    per=collections.defaultdict(set); flags={}
    for row in csv.DictReader(open(UHT)):
        per[row['owner']].add(row['func']); flags[(row['owner'],row['func'])]=row['flags']
    return per, flags

def build(dump='s129'):
    per,flags=load_uht()
    recs=rectab.scan(dump); groups=rectab.runs(recs)
    attrib={}   # (class,func) -> record
    runclass=[]
    for g in groups:
        names=set(r['name'] for r in g)
        scored=[(len(names&fs),cn) for cn,fs in per.items() if names&fs]
        if not scored: runclass.append((g,None,0)); continue
        scored.sort(reverse=True)
        best,cn=scored[0]
        tie=[c for s,c in scored if s==best]
        runclass.append((g,cn if len(tie)==1 else None,best))
        if len(tie)==1:
            for r in g:
                if r['name'] in per[cn]: attrib[(cn,r['name'])]=r
    return per,flags,attrib,runclass,recs

def classify(irv):
    if irv in rectab.FOLD: return 'EMPTY', rectab.FOLD[irv], ''
    cov=rectab.covered(irv)
    if not cov: return 'IMPL-PAGE-DARK','impl page dark in all 3 images',''
    data,base,secs=rectab.L(cov[0])
    b=data[irv:irv+12]
    if b[:2]==b'\x48\x8b' and b[2]==0x01 and b[3]==0xff and b[4]==0xa0:
        disp=struct.unpack_from('<I',b,5)[0]
        return 'VTABLE-FWD', f'mov rax,[rcx]; jmp [rax+{disp:#x}]', b.hex()
    return 'REAL','',b.hex()

if __name__=='__main__':
    per,flags,attrib,runclass,recs=build()
    print(f'# records={len(recs)} runs={len(runclass)} attributed_keys={len(attrib)}')
    print('\n## CONTROLS')
    ok=0; tot=0
    for cls,fn,exp in GOLD_EMPTY+GOLD_REAL:
        tot+=1; r=attrib.get((cls,fn))
        if r is None: print(f'  FAIL  {cls}::{fn:32s} NO RECORD (expected impl {exp:#x})'); continue
        v,d,b=classify(r['impl'])
        good = r['impl']==exp
        ok+=good
        print(f"  {'PASS' if good else 'FAIL'}  {cls}::{fn:32s} rec={r['rec']:#x} thunk={r['thunk']:#x} impl={r['impl']:#x} expected={exp:#x} -> {v}")
    print(f'  CONTROL HIT RATE: {ok}/{tot}')
    print('\n## SWEEP')
    keys=[]
    for cls in DROP_CLASSES:
        for fn in sorted(per.get(cls,())): keys.append((cls,fn))
    keys+= [k for k in EXTRA if k not in keys]
    print(f'  key count = {len(keys)}')
    for cls,fn in keys:
        r=attrib.get((cls,fn))
        if r is None:
            print(f'{cls}::{fn}\tNO-RECORD\t-\t-\t{flags.get((cls,fn),"")}')
        else:
            v,d,b=classify(r['impl'])
            print(f"{cls}::{fn}\t{v}\t{r['impl']:#x}\t{r['thunk']:#x}\t{flags.get((cls,fn),'')}\t{d}\t{b}")
