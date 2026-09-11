# S131 LANE D - report generator: writes the per-record TSV + path analysis.
import json, os, collections, csv

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
recs = json.load(open(os.path.join(ROOT,'scratchpad','s131','laneD','recs.json')))

FOLD = {0xF7EC20:'ret 0 (c2 00 00)', 0xF7EB50:'xor eax,eax; ret', 0xF7EB60:'xor al,al; ret',
        0xB9E1F0:'mov al,1; ret', 0xFC6CF0:'xorps xmm0,xmm0; ret  [5th fold, NEW S131]'}

out = os.path.join(ROOT,'scratchpad','s131','lane-d-empty-impl-census.tsv')
with open(out,'w',newline='',encoding='utf-8') as fh:
    w = csv.writer(fh, delimiter='\t', lineterminator='\n')
    w.writerow(['class','func','verdict','impl_rva','thunk_rva','fold_behaviour','impl_bytes16',
                'impl_src_image','thunk_page_lit','uht_flags','is_Net','rec_rva'])
    for r in sorted(recs, key=lambda x:(x['cls'], x['name'])):
        fl = r.get('flags') or ''
        w.writerow([r['cls'], r['name'], r['verdict'], '0x%x'%r['impl'], '0x%x'%r['thunk'],
                    FOLD.get(r['impl'],'') or (r.get('detail','') if r['verdict']!='REAL' else ''),
                    r.get('bytes',''), r.get('src_img',''), int(bool(r.get('thunk_lit'))),
                    fl, int('Net' in fl.split('|')), '0x%x'%r['rec']])
print('[wrote]', out, len(recs), 'rows')

byc = collections.defaultdict(list)
for r in recs: byc[r['cls']].append(r)

SCOPE1 = ['ALokiDropPlane','ULokiPlayerDropPlaneComponent','ULokiRideableComponent',
          'ALokiTeamState_TeamOnly','ALokiDropPodBase','ULokiGameModeDropPlaneComponent',
          'ULokiDropPhaseLibrary','ULokiDropPhaseDebuggingTool']
SCOPE2_EXTRA = ['ALokiRoundGameMode','ALokiGameMode','ALokiGameState','ALokiPlayerState',
                'ALokiCharacter','ALokiHeroCharacter','ULokiCharacterMovementComponent',
                'ALokiTeamState','ALokiDropOnDeathComponent','ULokiDropOnDeathComponent',
                'ALokiDropHidableActor','ULokiTeamComponent','ALokiBattleRoyaleSpawner']

def tab(title, classes):
    print('\n=== %s ===' % title)
    print('%-38s %5s %5s %6s %5s %5s'%('class','recs','REAL','EMPTY','FWD','DARK'))
    T=collections.Counter()
    for c in classes:
        rs = byc.get(c, [])
        v = collections.Counter(r['verdict'] for r in rs)
        T.update(v); T['n'] += len(rs)
        print('%-38s %5d %5d %6d %5d %5d'%(c,len(rs),v['REAL'],v['EMPTY'],v['FORWARDER'],v['IMPL-PAGE-DARK']))
    print('%-38s %5d %5d %6d %5d %5d'%('TOTAL',T['n'],T['REAL'],T['EMPTY'],T['FORWARDER'],T['IMPL-PAGE-DARK']))
    grad = T['REAL']+T['EMPTY']
    if grad: print('  EMPTY rate over gradeable (REAL+EMPTY): %.1f%%  (%d/%d)'%(100*T['EMPTY']/grad,T['EMPTY'],grad))
    emp = [r for c in classes for r in byc.get(c,[]) if r['verdict']=='EMPTY']
    print('  EMPTY names: ' + ', '.join('%s::%s'%(r['cls'],r['name']) for r in sorted(emp,key=lambda x:(x['cls'],x['name']))))
    return T

t1 = tab('SCOPE 1 - the 8 drop/rideable classes (FK-22 2.5 set C)', SCOPE1)
t2 = tab('SCOPE 2 - full deploy chain (scope 1 + round/gamemode/character/playerstate)', SCOPE1+SCOPE2_EXTRA)
