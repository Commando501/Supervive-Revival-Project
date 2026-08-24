import sys, json
sys.path.insert(0,'.')
from collections import defaultdict, Counter
d=json.load(open('stores_v3.json')); hits=d['hits']; fns={int(k):v for k,v in d['fns'].items()}
vt=json.load(open('cmc_vtables.json')); LOKI=set(vt['loki']); ENG=set(vt['eng'])
NAME={0x12B0:'TimeSinceFallingStart',0x16B0:'VelSnapshot',0x16C8:'VelSnapFlag',
      0x328:'Acceleration',0x231:'MovementMode',0x290:'MinAnalogWalkSpeed',0x3E4:'MaxSimIter',0x3E0:'MaxSimStep'}
RARE={0x12B0,0x16B0,0x16C8}
byfn=defaultdict(list)
for h in hits: byfn[h['fn']].append(h)

tiers=defaultdict(list)
for fb,hs in byfn.items():
    m=fns[fb]; sig=set(m['sigs'])
    # only NON-STACK stores can be object field writes
    obj=[h for h in hs if h['base'] not in ('rsp',) and not (h['base']=='rbp' and m['framebp'])]
    if not obj: continue
    why=[]
    t=None
    if fb in LOKI and fb in ENG: why.append('CMC-VTABLE(shared slot)'); t='A'
    elif fb in LOKI: why.append('CMC-VTABLE(LOKI-ONLY = Loki override)'); t='A'
    elif fb in ENG: why.append('CMC-VTABLE(ENGINE-ONLY = overridden by Loki)'); t='A'
    if sig & RARE:
        why.append('RARE-CMC-FIELD:'+','.join(NAME[x] for x in sorted(sig&RARE))); t=t or 'B'
    if len(sig-RARE)>=2:
        why.append('CMC-FIELDS:'+','.join(NAME[x] for x in sorted(sig-RARE))); t=t or 'C'
    if m['ccmc']: why.append('CALLS-GetLokiCharacterMovement'); t=t or 'C'
    if m['l458']: why.append('LOADS-ACharacter+0x458')
    if t: tiers[t].append((fb,m,obj,why))

for t in 'ABC':
    print(f"TIER {t}: {len(tiers[t])} functions, {sum(len(o) for _,_,o,_ in tiers[t])} object-field stores")
print()
for t in 'AB':
    print(f"\n################ TIER {t} ################")
    for fb,m,obj,why in sorted(tiers[t]):
        print(f"\nFN {fb:#09x}  insns={m['n']}  [{'; '.join(why)}]")
        for h in obj:
            print(f"   {h['rva']:#09x} {h['mnem']:8s} {h['op']:38s} base={h['base']}{'  RMW' if h['rmw'] else ''}")
json.dump({t:[[fb,m,obj,why] for fb,m,obj,why in v] for t,v in tiers.items()}, open('cmc_tiers3.json','w'))
