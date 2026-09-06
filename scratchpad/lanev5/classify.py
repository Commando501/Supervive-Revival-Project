import sys, struct, json, csv, bisect
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
data=load(); IB,secs=pehdr(data)
def u64(a): return struct.unpack_from('<Q',data,a)[0]
VT={'AController':(0x08010428,289),'AAIController':(0x08431398,308),
    'ADetourCrowdAIController':(0x0845AAC0,308),'AGridPathAIController':(0x0845AAC0,308),
    'ALokiAIController':(0x08878580,310),'ALokiBotController':(0x088CDE18,310),
    'ALokiMinionAIController':(0x089F8078,310),'APlayerController':(0x081A82F8,512),
    'ALokiPlayerController':(0x08A1AEE0,586)}
slot={}
for c,(vt,n) in VT.items():
    for i in range(n):
        v=u64(vt+i*8)
        if IB<v<IB+0xB000000: slot.setdefault(v-IB,[]).append((c,i))

h=json.load(open('scratchpad/lanev5/hits2.json'))
W=[x for x in h if x['dst'] and x['mnem'] not in ('call','jmp','cmp','test') and x['base']!='rsp']
R=[x for x in h if not x['dst']]
print("disp-0x488 decoded: %d | mem-DEST non-stack real writes: %d" % (len(h), len(W)))

def bit20(x):
    m=x['mnem']; imm=x['imm']
    if m=='and' and imm is not None:
        return 'CLEARS bit0x20' if (imm & 0x20)==0 else 'preserves bit0x20 (and-mask has bit set)'
    if m in ('or','xor') and imm is not None:
        return ('SETS/FLIPS bit0x20' if (imm & 0x20) else 'does NOT touch bit0x20')
    if m=='mov' and imm is not None:
        return 'OVERWRITES field: bit0x20 -> %d' % (1 if (imm & 0x20) else 0)
    return 'DEPENDS ON REGISTER VALUE (RMW/store) -- needs dataflow'
print("\n=== ALL non-stack writes to [reg+0x488]  (n=%d) ===" % len(W))
fam=[]
for x in sorted(W,key=lambda z:z['rva']):
    tags=slot.get(x['fn_b'],[]) if x['fn_b'] else []
    if tags: fam.append((x,tags))
print("of which containing fn is a virtual method of an (AI)Controller vtable: %d" % len(fam))
for x,t in fam:
    print("  0x%08X fn=0x%X  %-30s %s %s\n       -> %s\n       -> slots %s" % (
        x['rva'],x['fn_b'],x['bytes'],x['mnem'],x['ops'],bit20(x),t[:8]))
json.dump([x for x in W], open('scratchpad/lanev5/writes_nonstack.json','w'))
