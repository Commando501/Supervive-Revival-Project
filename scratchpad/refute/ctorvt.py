import struct,csv,bisect,json
from capstone import *
from capstone.x86 import *
d=open(r"dumps/merged12.dump.exe",'rb').read()
IB=0x7ff6af000000
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
w=[x for x in json.load(open("scratchpad/refute/writes.json")) if x[2]!='call']
fns=sorted(set(int(x[4],16) for x in w))
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
# AController-family vtables: any vtable whose slot 273 target set matches controllers.
# Build robust: vtables containing 0x36DEE20 at slot 273 OR 0x45D6D10 at slot 177.
out={}
for f in fns:
    c=chain(f)
    if not c: continue
    b,e=c
    lea={}
    vts=set()
    for ins in md.disasm(d[b:e],b):
        if ins.mnemonic=='lea' and len(ins.operands)==2 and ins.operands[1].type==X86_OP_MEM and ins.operands[1].mem.base==X86_REG_RIP:
            lea[ins.operands[0].reg]=ins.address+ins.size+ins.operands[1].mem.disp
        elif ins.mnemonic=='mov' and len(ins.operands)==2 and ins.operands[0].type==X86_OP_MEM and ins.operands[1].type==X86_OP_REG:
            if ins.operands[0].mem.disp==0 and ins.operands[1].reg in lea:
                vts.add(lea[ins.operands[1].reg])
    if vts: out[hex(f)]=[hex(v) for v in sorted(vts)]
json.dump(out,open("scratchpad/refute/ctorvt.json","w"),indent=0)
print("writer fns that install >=1 vtable:",len(out),"of",len(fns))
for k,v in out.items(): print(" ",k,v)
