import sys,json
sys.path.insert(0,'scratchpad/refute-x2')
from pe import PE
import capstone
from capstone.x86 import X86_REG_EFLAGS
p=PE('dumps/merged13.dump.exe'); d=p.data
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64); md.detail=True
hits=json.load(open('scratchpad/refute-x2/hits.json'))
AUTH={'je','jae','jz','jnb','jnc','sete','cmove','cmovae'}
NOTAUTH={'jne','jb','jnz','jnae','jc','setne','setb','cmovne','cmovb'}
res={}
rows=[]
for s,ops,by in hits:
    start=s+len(by)//2
    buf=bytes(d[start:start+64])
    verdict=None; n=0; detail=[]
    for ins in md.disasm(buf,start):
        n+=1
        if n>8: break
        r,w=ins.regs_access()
        detail.append((hex(ins.address),ins.mnemonic,ins.op_str))
        if X86_REG_EFLAGS in r:
            m=ins.mnemonic
            if m in AUTH: verdict=('AUTH',m,n)
            elif m in NOTAUTH: verdict=('NOTAUTH',m,n)
            else: verdict=('OTHER:'+m,m,n)
            break
        if X86_REG_EFLAGS in w:
            verdict=('CLOBBER',ins.mnemonic,n); break
    if verdict is None: verdict=('NOCONSUMER','',0)
    rows.append((s,ops,verdict,detail[:4]))
    res[verdict[0].split(':')[0]]=res.get(verdict[0].split(':')[0],0)+1
print(res)
from collections import Counter
print('AUTH mnemonics',Counter(v[1] for _,_,v,_ in rows if v[0]=='AUTH'))
print('AUTH dist-from-cmp',Counter(v[2] for _,_,v,_ in rows if v[0]=='AUTH'))
print('NOTAUTH mnemonics',Counter(v[1] for _,_,v,_ in rows if v[0]=='NOTAUTH'))
print('OTHER:',[ (hex(s),v) for s,o,v,dd in rows if v[0] not in ('AUTH','NOTAUTH')])
json.dump([[s,ops,v[0],v[1],v[2]] for s,ops,v,dd in rows],open('scratchpad/refute-x2/cls.json','w'))
