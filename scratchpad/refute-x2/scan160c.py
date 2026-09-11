import sys,json,collections; sys.path.insert(0,'scratchpad/refute-x2')
from pe import PE
import capstone
p=PE('dumps/merged13.dump.exe'); d=p.data
t=p.sec('.text'); lo=t['vaddr']; hi=t['vaddr']+t['vsize']
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
tail=b'\x60\x01\x00\x00\x03'
def decode_at(s,ln):
    b=bytes(d[s:s+ln])
    try: ins=next(md.disasm(b,s))
    except StopIteration: return None
    if ins.size!=ln or ins.mnemonic!='cmp': return None
    ops=ins.operands
    if len(ops)!=2 or ops[0].type!=capstone.x86.X86_OP_MEM: return None
    if not ins.op_str.startswith('byte'): return None
    if ops[0].mem.disp!=0x160: return None
    if ops[1].type!=capstone.x86.X86_OP_IMM or ops[1].imm!=3: return None
    return ins
def anchor_vote(cands):
    # linear-disassemble from anchors behind; count which candidate start the chain lands on
    v=collections.Counter()
    s0=min(cands)
    for back in range(8,48):
        a=s0-back
        for ins in md.disasm(bytes(d[a:s0+16]),a):
            if ins.address in cands: v[ins.address]+=1; break
            if ins.address>max(cands): break
    return v
hits=[]; amb=[]
i=lo
while True:
    j=d.find(tail,i,hi)
    if j<0: break
    i=j+1
    cands={}
    for back in (2,3,4):
        s=j-back
        ins=decode_at(s,back+5)
        if ins: cands[s]=ins
    if not cands: continue
    if len(cands)==1:
        s=list(cands)[0]
    else:
        v=anchor_vote(set(cands))
        if not v: s=max(cands); amb.append(hex(s))
        else: s=v.most_common(1)[0][0]
    ins=cands[s]
    hits.append((s,ins.op_str,ins.bytes.hex()))
print('confirmed',len(hits),'ambiguous-unresolved',len(amb),amb)
c=collections.Counter(h[1].split('[')[1].split('+')[0].strip() for h in hits)
print(sorted(c.items(),key=lambda kv:-kv[1]))
json.dump(hits,open('scratchpad/refute-x2/hits_anchored.json','w'))
