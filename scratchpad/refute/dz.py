import sys,csv,bisect
from capstone import *
d=open(r"dumps/merged12.dump.exe",'rb').read()
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
md=Cs(CS_ARCH_X86,CS_MODE_64)
a=int(sys.argv[1],16)
c=chain(a)
if len(sys.argv)>2: b,e=a,a+int(sys.argv[2],16)
else:
    if c is None: b,e=a,a+0x200; print("NO PDATA ROW -- using 0x200 window")
    else: b,e=c
print(f"extent {b:#x}..{e:#x} size {e-b}")
for ins in md.disasm(d[b:e],b):
    print(f"{ins.address:#x}  {ins.bytes.hex():24s} {ins.mnemonic} {ins.op_str}")
