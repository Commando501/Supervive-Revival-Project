import sys, json, csv, bisect, capstone
sys.path.insert(0,'scratchpad/lanev5')
from pe import load, pehdr
from capstone.x86 import X86_OP_MEM, X86_OP_IMM, X86_OP_REG
data=load(); IB,secs=pehdr(data)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
prows=[]
with open('tools/strxref/index/pdata_union.csv') as f:
    for x in csv.DictReader(f): prows.append((int(x['begin_rva'],16),int(x['end_rva'],16)))
prows.sort(); pbeg=[a for a,_ in prows]
def ext(rva):
    i=bisect.bisect_right(pbeg,rva)-1
    if i<0: return None
    b,e=prows[i]
    if not(b<=rva<e): return None
    j=i
    while j>0 and prows[j-1][1]==prows[j][0]: j-=1
    k=i
    while k+1<len(prows) and prows[k][1]==prows[k+1][0]: k+=1
    return (prows[j][0],prows[k][1])

h=json.load(open('scratchpad/lanev5/hits2.json'))
leas=[x for x in h if x['mnem']=='lea']
print("=== ALIAS PASS: %d `lea Rx,[Rb+0x488]` sites; scan each containing function for writes through Rx at disp 0..3 ===" % len(leas))
tot_w=0
for x in sorted(leas,key=lambda z:z['rva']):
    e = (x['fn_b'],x['fn_e']) if x['fn_b'] else ext(x['rva']) or (x['rva']-0x20, x['rva']+0x300)
    ins=list(md.disasm(data[e[0]:e[1]], e[0]))
    # locate lea, get dest reg
    dst=None; k=None
    for i,z in enumerate(ins):
        if z.address==x['rva'] and z.mnemonic=='lea':
            dst=z.operands[0].reg; k=i; break
    if dst is None: 
        print("  0x%08X  (could not re-locate in linear disasm; fn 0x%X..0x%X)"%(x['rva'],e[0],e[1])); continue
    name=ins[k].reg_name(dst)
    uses=[]
    for z in ins[k+1:]:
        # stop if dest reg overwritten by a non-mem-use def
        for op in z.operands:
            if op.type==X86_OP_MEM and op.mem.base==dst and 0<=op.mem.disp<=7:
                iswrite = (z.operands[0].type==X86_OP_MEM and z.operands[0].mem.base==dst)
                imm=None
                for o in z.operands:
                    if o.type==X86_OP_IMM: imm=o.imm
                uses.append((z.address,z.mnemonic,z.op_str,'WRITE' if iswrite and z.mnemonic not in('cmp','test') else 'read',imm,op.mem.disp))
        if z.mnemonic in ('lea','mov','xor','pop') and z.operands and z.operands[0].type==X86_OP_REG and z.operands[0].reg==dst:
            if not (z.mnemonic=='mov' and len(z.operands)>1 and z.operands[1].type==X86_OP_MEM and z.operands[1].mem.base==dst):
                break
    w=[u for u in uses if u[3]=='WRITE']
    tot_w+=len(w)
    print("  0x%08X fn=0x%X-> %s : %d use(s) via %s ; WRITES=%d" % (x['rva'],e[0],name,len(uses),name,len(w)))
    for u in uses:
        flag=''
        if u[3]=='WRITE':
            if u[4] is not None and u[1]=='and': flag=' <== CLEARS bit0x20' if (u[4]&0x20)==0 and u[5]==0 else ' (mask keeps 0x20)'
            elif u[4] is not None and u[1] in ('or','xor'): flag=' <== TOUCHES bit0x20' if (u[4]&0x20) and u[5]==0 else ''
            else: flag=' <== register/other write, disp+%d'%u[5]
        print("        %-5s 0x%08X %s %s%s"%(u[3],u[0],u[1],u[2],flag))
print("TOTAL aliased writes found: %d"%tot_w)
