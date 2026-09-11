import sys, struct, json, csv, bisect
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
data=load(); IB,secs=pehdr(data)
def u64(a): return struct.unpack_from('<Q',data,a)[0]
VT = {
 'AController':(0x08010428,289),
 'AAIController':(0x08431398,308),
 'ADetourCrowdAIController':(0x0845AAC0,308),
 'AGridPathAIController':(0x0845AAC0,308),
 'ALokiAIController':(0x08878580,310),
 'ALokiBotController':(0x088CDE18,310),
 'ALokiMinionAIController':(0x089F8078,310),
}
slotfn={}   # rva -> set of (class,slot)
for cls,(vt,n) in VT.items():
    for i in range(n):
        v=u64(vt+i*8)
        if IB<v<IB+0xB000000:
            slotfn.setdefault(v-IB,set()).add((cls,i))
print("AController-family virtual method RVAs (union): %d" % len(slotfn), file=sys.stderr)

prows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f):
        prows.append((int(x['begin_rva'],16), int(x['end_rva'],16)))
prows.sort(); pbeg=[a for a,_ in prows]
def chain_entry(rva):
    i=bisect.bisect_right(pbeg,rva)-1
    if i<0: return None
    b,e=prows[i]
    if not(b<=rva<e): return None
    j=i
    while j>0 and prows[j-1][1]==prows[j][0]: j-=1
    return prows[j][0]

cand=json.load(open('scratchpad/lanev5/writers488.json'))
hits=[]
for x in cand:
    fn=x['fn']
    tags=set()
    for probe in ([fn] if fn else []):
        if probe in slotfn: tags|=slotfn[probe]
    # also check the raw rva's own chain entry
    ce=chain_entry(x['rva'])
    if ce and ce in slotfn: tags|=slotfn[ce]
    if tags:
        hits.append((x,sorted(tags)))
print("\n=== WRITERS to [reg+0x488] whose containing function IS a virtual method of an AController-family vtable ===")
for x,t in sorted(hits,key=lambda z:z[0]['rva']):
    print("  0x%08X fn=%s  %-30s %s %s\n        vtable-slot: %s" % (x['rva'], ('0x%X'%x['fn']) if x['fn'] else 'NO-PDATA', x['bytes'], x['mnem'], x['ops'], t[:6]))
print("  count:", len(hits))
