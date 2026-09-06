import sys, capstone, csv, bisect
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
from capstone.x86 import X86_OP_MEM
data=load(); IB,secs=pehdr(data)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
prows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f): prows.append((int(x['begin_rva'],16),int(x['end_rva'],16)))
prows.sort(); pbeg=[a for a,_ in prows]
def ext(r):
    i=bisect.bisect_right(pbeg,r)-1
    if i<0: return None
    b,e=prows[i]
    if not(b<=r<e): return None
    j=i; 
    while j>0 and prows[j-1][1]==prows[j][0]: j-=1
    k=i
    while k+1<len(prows) and prows[k][1]==prows[k+1][0]: k+=1
    return (prows[j][0],prows[k][1])
def real_ctor(ithunk):
    """InternalConstructor<T> tail-jumps/jne to the real ctor"""
    for ins in md.disasm(data[ithunk:ithunk+0x30], ithunk):
        if ins.mnemonic in ('jmp','jne','je') and ins.op_str.startswith('0x'):
            t=int(ins.op_str,16)
            if abs(t-ithunk)>0x40: return t
    return None
print("%-32s %-12s %-12s %-24s %s"%("class","IntCtor","realCtor","extent","disp-0x488 instructions"))
for line in open('scratchpad/lanev5/ctors.txt'):
    c,a=line.split(); ic=int(a,16); rc=real_ctor(ic)
    if rc is None: print("%-32s 0x%-10X  <no tail jump>"%(c,ic)); continue
    e=ext(rc) or (rc, rc+0x400)
    p=rc&~0xFFF
    hits=[]
    for ins in md.disasm(data[e[0]:e[1]], e[0]):
        for op in ins.operands:
            if op.type==X86_OP_MEM and op.mem.disp==0x488 and op.mem.base!=0:
                hits.append("0x%08X %s %s [%s]"%(ins.address,ins.mnemonic,ins.op_str,' '.join('%02x'%x for x in ins.bytes)))
    print("%-32s 0x%-10X 0x%-10X 0x%X..0x%X lit=%s  %s"%(c,ic,rc,e[0],e[1],bool(any(data[p:p+0x1000])), hits if hits else "NONE"))
