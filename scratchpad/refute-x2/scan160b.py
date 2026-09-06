import sys,json
sys.path.insert(0,'scratchpad/refute-x2')
from pe import PE
import capstone
p=PE('dumps/merged13.dump.exe'); d=p.data
t=p.sec('.text'); lo=t['vaddr']; hi=t['vaddr']+t['vsize']
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
tail=b'\x60\x01\x00\x00\x03'
hits=[]; raw=0; i=lo
while True:
    j=d.find(tail,i,hi)
    if j<0: break
    raw+=1; i=j+1
    best=None
    for back in (4,3,2):   # prefer LONGEST (REX/SIB present)
        s=j-back
        if s<lo: continue
        b=bytes(d[s:j+5])
        try: ins=next(md.disasm(b,0))
        except StopIteration: continue
        if ins.size!=len(b) or ins.mnemonic!='cmp': continue
        ops=ins.operands
        if len(ops)!=2 or ops[0].type!=capstone.x86.X86_OP_MEM: continue
        if not ins.op_str.startswith('byte'): continue
        if ops[0].mem.disp!=0x160: continue
        if ops[1].type!=capstone.x86.X86_OP_IMM or ops[1].imm!=3: continue
        best=(s,ins.op_str,b.hex()); break
    if best: hits.append(best)
print('raw',raw,'confirmed',len(hits))
from collections import Counter
c=Counter(h[1].split('[')[1].split('+')[0].strip() for h in hits)
print(sorted(c.items(),key=lambda kv:-kv[1]))
json.dump(hits,open('scratchpad/refute-x2/hits.json','w'))
