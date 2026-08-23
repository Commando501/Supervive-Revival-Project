import sys,json,collections; sys.path.insert(0,'scratchpad/refute-x2')
from pe import PE
import capstone
p=PE('dumps/merged13.dump.exe'); d=p.data
t=p.sec('.text'); lo=t['vaddr']; hi=t['vaddr']+t['vsize']
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
disp=b'\x60\x01\x00\x00'
found=collections.defaultdict(list)
i=lo
tot=0
while True:
    j=d.find(disp,i,hi)
    if j<0: break
    i=j+1; tot+=1
    # try instruction starts from j-8 .. j-2, longest first, must END exactly at j+4
    for back in range(8,1,-1):
        s=j-back
        if s<lo: continue
        b=bytes(d[s:j+4])
        try: ins=next(md.disasm(b,s))
        except StopIteration: continue
        if ins.size!=len(b): continue
        ops=ins.operands
        if not ops or ops[-1].type!=capstone.x86.X86_OP_MEM: 
            if not (len(ops)>=1 and ops[0].type==capstone.x86.X86_OP_MEM): continue
        mem=None
        for o in ops:
            if o.type==capstone.x86.X86_OP_MEM and o.mem.disp==0x160: mem=o
        if mem is None: continue
        if mem.size!=1: continue   # byte-sized memory operand
        found[ins.mnemonic].append((s,ins.op_str,ins.bytes.hex()))
        break
print('total 0x00000160 disp32 occurrences scanned in .text:',tot)
for m,v in sorted(found.items(),key=lambda kv:-len(kv[1])):
    print('%-8s %d'%(m,len(v)))
json.dump({m:[[a,o,b] for a,o,b in v] for m,v in found.items()},open('scratchpad/refute-x2/scan2.json','w'))
# for movzx/movsx/mov: look for a following cmp reg,imm within 6 insns
def follow(addr,ln):
    out=[]
    for ins in md.disasm(bytes(d[addr+ln:addr+ln+48]),addr+ln):
        out.append((ins.mnemonic,ins.op_str))
        if len(out)>=6: break
    return out
for m in ('movzx','movsx','mov'):
    for s,o,b in found.get(m,[]):
        f=follow(s,len(b)//2)
        cs=[x for x in f if x[0]=='cmp' and x[1].endswith((', 3',', 2',', 1',', 0'))]
        if cs:
            print(m,hex(s),o,'->',f[:4])
