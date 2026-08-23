import sys,json
sys.path.insert(0,'scratchpad/refute-x2')
from pe import PE
import capstone
p=PE('dumps/merged13.dump.exe'); d=p.data
t=p.sec('.text'); lo=t['vaddr']; hi=t['vaddr']+t['vsize']
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64)
md.detail=True
tail=b'\x60\x01\x00\x00\x03'
hits=[]; raw=0
i=lo
while True:
    j=d.find(tail,i,hi)
    if j<0: break
    raw+=1
    i=j+1
    # candidate starts: try up to 3 bytes back (rex? opcode modrm [sib])
    for back in (2,3,4):   # opcode+modrm=2 ; +rex or +sib =3 ; rex+sib=4
        s=j-back
        if s<lo: continue
        b=d[s:j+5]
        try:
            ins=next(md.disasm(bytes(b),0))
        except StopIteration:
            continue
        if ins.size!=len(b): continue
        if ins.mnemonic!='cmp': continue
        ops=ins.operands
        if len(ops)!=2: continue
        if ops[0].type!=capstone.x86.X86_OP_MEM: continue
        if ins.op_str.split()[0]!='byte': continue
        if ops[0].mem.disp!=0x160: continue
        if ops[1].type!=capstone.x86.X86_OP_IMM or ops[1].imm!=3: continue
        hits.append((s,ins.op_str,ins.bytes.hex()))
        break
print('raw tail occurrences in .text:',raw)
print('confirmed cmp byte[+0x160],3 :',len(hits))
from collections import Counter
c=Counter()
for s,ops,by in hits:
    reg=ops.split('[')[1].split('+')[0]
    c[reg]+=1
print(sorted(c.items(),key=lambda kv:-kv[1]))
json.dump([[h[0],h[1],h[2]] for h in hits],open('scratchpad/refute-x2/hits.json','w'))
