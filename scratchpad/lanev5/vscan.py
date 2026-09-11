import sys, struct, csv, bisect, capstone
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
from capstone.x86 import X86_OP_MEM
data=load(); IB,secs=pehdr(data)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
def u64(a): return struct.unpack_from('<Q',data,a)[0]
prows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f): prows.append((int(x['begin_rva'],16),int(x['end_rva'],16)))
prows.sort(); pbeg=[a for a,_ in prows]
def ext(r):
    i=bisect.bisect_right(pbeg,r)-1
    if i<0: return None
    b,e=prows[i]
    if not(b<=r<e): return None
    j=i
    while j>0 and prows[j-1][1]==prows[j][0]: j-=1
    k=i
    while k+1<len(prows) and prows[k][1]==prows[k+1][0]: k+=1
    return (prows[j][0],prows[k][1])
VT={'AController':(0x08010428,289),'AAIController':(0x08431398,308),
    'ADetourCrowdAIController':(0x0845AAC0,308),'AGridPathAIController':(0x0845AAC0,308),
    'ALokiAIController':(0x08878580,310),'ALokiBotController':(0x088CDE18,310),
    'ALokiMinionAIController':(0x089F8078,310)}
FOLD={0xF7EC20,0xF7EB50,0xF7EB60,0xB9E1F0,0xFC6CF0}
targets={}
for c,(vt,n) in VT.items():
    for i in range(n):
        v=u64(vt+i*8)
        if IB<v<IB+0xB000000:
            targets.setdefault(v-IB,[]).append((c,i))
print("Distinct virtual-method targets across the 7 AIController-family classes: %d"%len(targets))
dark=0; scanned=0; found=[]
for r,who in sorted(targets.items()):
    p=r&~0xFFF
    if not any(data[p:p+0x1000]):
        dark+=1; continue
    if r in FOLD: continue
    e=ext(r) or (r, r+0x600)
    scanned+=1
    for ins in md.disasm(data[e[0]:e[1]], e[0]):
        for op in ins.operands:
            if op.type==X86_OP_MEM and op.mem.disp==0x488 and op.mem.base!=0:
                isw = ins.operands[0].type==X86_OP_MEM and ins.operands[0].mem.disp==0x488 and ins.mnemonic not in ('cmp','test','call','jmp','lea')
                found.append((ins.address,'WRITE' if isw else 'READ ',ins.mnemonic,ins.op_str,r,who))
print("  scanned bodies: %d ; DARK targets skipped: %d"%(scanned,dark))
print("\nEvery disp-0x488 instruction inside an (AI)Controller-family VIRTUAL METHOD body:")
seen=set()
for a,k,m,o,r,who in sorted(found):
    if a in seen: continue
    seen.add(a)
    print("  %s 0x%08X  %-38s   in fn 0x%08X  = %s"%(k,a,"%s %s"%(m,o),r,", ".join("%s:slot%d"%w for w in who[:4])))
print("\nWRITES: %d   READS: %d"%(sum(1 for a in seen if any(x[0]==a and x[1]=='WRITE' for x in found)),
                                 sum(1 for a in seen if any(x[0]==a and x[1]=='READ ' for x in found))))
