import sys, struct, capstone, csv, bisect, json
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_OP_REG

DISP=0x488
data=load(); IB,secs=pehdr(data)
tx=[s for s in secs if s['name']=='.text'][0]
TB,TE=tx['vaddr'],tx['vaddr']+tx['vsize']
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
needle=struct.pack('<i',DISP)

NP=(TE-TB+0xFFF)//0x1000
lit=bytearray(NP)
for i in range(NP):
    p=TB+i*0x1000
    if any(data[p:p+0x1000]): lit[i]=1

prows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f):
        prows.append((int(x['begin_rva'],16),int(x['end_rva'],16)))
prows.sort(); pbeg=[a for a,_ in prows]
def chain(rva):
    i=bisect.bisect_right(pbeg,rva)-1
    if i<0: return None
    b,e=prows[i]
    if not(b<=rva<e): return None
    j=i
    while j>0 and prows[j-1][1]==prows[j][0]: j-=1
    k=i
    while k+1<len(prows) and prows[k][1]==prows[k+1][0]: k+=1
    return (prows[j][0], prows[k][1])

# collect occurrences
occ=[]
pos=TB
while True:
    p=data.find(needle,pos,TE)
    if p<0: break
    pos=p+1
    if lit[(p-TB)//0x1000]: occ.append(p)
print("[occ] 88 04 00 00 in LIT .text: %d"%len(occ), file=sys.stderr)

# group by containing function
funcs={}
nopd=[]
for p in occ:
    c=chain(p)
    if c is None: nopd.append(p)
    else: funcs.setdefault(c,[]).append(p)
print("[occ] inside a .pdata function: %d occurrences in %d functions ; NO-PDATA: %d"%(
    sum(len(v) for v in funcs.values()), len(funcs), len(nopd)), file=sys.stderr)

def linear(b,e):
    """exact linear disasm of [b,e); returns list of insns"""
    out=[]
    for ins in md.disasm(data[b:e], b):
        out.append(ins)
    return out

results=[]
for (b,e),ps in sorted(funcs.items()):
    insns=linear(b,e)
    idx={i.address:k for k,i in enumerate(insns)}
    for k,ins in enumerate(insns):
        hit=False
        for op in ins.operands:
            if op.type==X86_OP_MEM and op.mem.disp==DISP and op.mem.base!=0:
                hit=True; mem=op; break
        if not hit: continue
        # is the mem operand a destination?  (capstone: first operand)
        dst_mem = (ins.operands[0].type==X86_OP_MEM and ins.operands[0].mem.disp==DISP)
        base = ins.reg_name(mem.mem.base)
        imm=None
        for op in ins.operands:
            if op.type==X86_OP_IMM: imm=op.imm
        results.append(dict(rva=ins.address, size=ins.size, fn_b=b, fn_e=e,
            bytes=' '.join('%02x'%x for x in ins.bytes), mnem=ins.mnemonic, ops=ins.op_str,
            dst=dst_mem, base=base, imm=imm, idx=k, exact=True))
# no-pdata: longest-valid heuristic
PREFIX=set(list(range(0x40,0x50))+[0x66,0x67,0xF0,0xF2,0xF3,0x2E,0x36,0x3E,0x26,0x64,0x65])
for p in nopd:
    best=None
    for k in range(12,1,-1):
        st=p-k
        if st<TB: continue
        if any(data[st+i] not in PREFIX for i in range(0, min(k-1,4))) and k>2:
            pass
        try: ins=next(md.disasm(data[st:st+16],st,1))
        except StopIteration: continue
        if ins.address+ins.size < p+4: continue
        if ins.disp_offset==0 or st+ins.disp_offset!=p: continue
        ok=any(op.type==X86_OP_MEM and op.mem.disp==DISP for op in ins.operands)
        if not ok: continue
        best=ins   # keep going -> smaller k overwrites; we want LARGEST k => break now
        break
    if best is None: continue
    ins=best
    mem=[op for op in ins.operands if op.type==X86_OP_MEM and op.mem.disp==DISP][0]
    dst_mem=(ins.operands[0].type==X86_OP_MEM and ins.operands[0].mem.disp==DISP)
    imm=None
    for op in ins.operands:
        if op.type==X86_OP_IMM: imm=op.imm
    results.append(dict(rva=ins.address,size=ins.size,fn_b=None,fn_e=None,
        bytes=' '.join('%02x'%x for x in ins.bytes),mnem=ins.mnemonic,ops=ins.op_str,
        dst=dst_mem, base=ins.reg_name(mem.mem.base) if mem.mem.base else None, imm=imm, idx=None, exact=False))

results.sort(key=lambda r:r['rva'])
print("[decode] exact-linear instructions with mem disp 0x488: %d ; heuristic(no-pdata): %d"%(
    sum(1 for r in results if r['exact']), sum(1 for r in results if not r['exact'])), file=sys.stderr)
json.dump(results, open('scratchpad/lanev5/hits2.json','w'))
