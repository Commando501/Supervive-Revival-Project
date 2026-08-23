import struct,csv,bisect,json
from capstone import *
from capstone.x86 import *
d=open(r"dumps/merged12.dump.exe",'rb').read()
IB=0x7ff6af000000
lit=open("scratchpad/refute/litpages.bin",'rb').read()
def islit(a):
    if not (0x1000<=a<0x1000+0x7649000): return False
    return bool(lit[(a-0x1000)//0x1000])
rows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for r in csv.DictReader(f): rows.append((int(r['begin_rva'],16),int(r['end_rva'],16)))
rows.sort(); begins=[r[0] for r in rows]
def chain(a):
    i=bisect.bisect_right(begins,a)-1
    if i<0: return None
    b,e=rows[i]
    if not (b<=a<e): return None
    lo=i
    while lo>0 and rows[lo-1][1]==rows[lo][0]: lo-=1
    hi=i
    while hi+1<len(rows) and rows[hi][1]==rows[hi+1][0]: hi+=1
    return rows[lo][0],rows[hi][1]
VT={'AController':(0x08010428,289),'AAIController':(0x08431398,308),'ADetourCrowd/AGridPath':(0x0845AAC0,308),
    'ALokiAIController':(0x08878580,310),'ALokiBotController':(0x088CDE18,310),'ALokiMinionAIController':(0x089F8078,310)}
FOLDS={0x00F7EC20,0x00F7EB50,0x00F7EB60,0x00B9E1F0,0x00FC6CF0}
tg=set()
for n,(vt,ns) in VT.items():
    for s in range(ns):
        r=struct.unpack_from('<Q',d,vt+s*8)[0]-IB
        tg.add(r)
tg |= {0x45D17D0,0x554B430,0x56196C0,0x3BBF3C0,0x3B809D0,0x36DEE20,0x36E2B60,0x36E3000}
tg -= FOLDS
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
scanned=0; dark=0; nopd=0
cover=[]; d488=[]
for f in sorted(tg):
    if not islit(f): dark+=1; continue
    c=chain(f)
    if c is None: b,e=f,f+0x400; nopd+=1
    else: b,e=c
    scanned+=1
    for ins in md.disasm(d[b:e],b):
        for i,op in enumerate(ins.operands):
            if op.type!=X86_OP_MEM: continue
            D=op.mem.disp
            if D==0x488: d488.append((hex(ins.address),ins.mnemonic,ins.op_str,hex(f)))
            elif 0x449<=D<0x488 and D+op.size>0x488:
                cover.append((hex(ins.address),ins.mnemonic,ins.op_str,op.size,hex(f)))
print("family fn targets:",len(tg),"scanned",scanned,"dark-skipped",dark,"no-pdata-window",nopd)
print("disp==0x488 instructions in family bodies:",len(d488))
for x in d488: print("   ",x)
print("WIDE stores/accesses covering byte 0x488 (disp<0x488, size spans it):",len(cover))
for x in cover: print("   ",x)
