import struct,csv,bisect,json
from capstone import *
from capstone.x86 import *
d=open(r"dumps/merged12.dump.exe",'rb').read()
TEXT_VA=0x1000; TEXT_SZ=0x7649000
lit=open("scratchpad/refute/litpages.bin",'rb').read()
def islit(a):
    if not (TEXT_VA<=a<TEXT_VA+TEXT_SZ): return False
    return bool(lit[(a-TEXT_VA)//0x1000])
rows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for r in csv.DictReader(f):
        rows.append((int(r['begin_rva'],16),int(r['end_rva'],16)))
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
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
occ=json.load(open("scratchpad/refute/occ488.json"))
occset=set(occ)
# group by containing chain
fns={}
noch=[]
for o in occ:
    c=chain(o)
    if c is None: noch.append(o); continue
    fns.setdefault(c,[]).append(o)
print("occurrences",len(occ),"in-chain-fns",len(fns),"in-chain-occ",sum(len(v) for v in fns.values()),"no-chain-occ",len(noch))
hits=[]
for (b,e),os in fns.items():
    if not islit(b): continue
    code=d[b:e]
    for ins in md.disasm(code,b):
        for op in ins.operands:
            if op.type==X86_OP_MEM and op.mem.disp==0x488:
                hits.append((ins.address,ins.size,ins.bytes.hex(),ins.mnemonic,ins.op_str,b,e))
                break
print("exact-decoded disp0x488 instructions:",len(hits))
json.dump([(hex(h[0]),h[1],h[2],h[3],h[4],hex(h[5]),hex(h[6])) for h in hits],open("scratchpad/refute/hits_exact.json","w"),indent=0)
# how many occurrences covered?
cov=set()
for h in hits:
    for k in range(h[1]):
        cov.add(h[0]+k)
missed=[o for o in occ if o in [x[0] for x in []]]
print("no-chain occurrences:",[hex(x) for x in noch][:20],"...total",len(noch))
