import json
from capstone import *
from capstone.x86 import *
hits=json.load(open("scratchpad/refute/hits_exact.json"))
STACK={'rsp','rbp','esp','ebp'}
md=Cs(CS_ARCH_X86,CS_MODE_64); md.detail=True
writes=[]
reads=[]
for a,sz,by,mn,ops,fb,fe in hits:
    ins=next(md.disasm(bytes.fromhex(by),int(a,16)))
    memop=None
    for i,op in enumerate(ins.operands):
        if op.type==X86_OP_MEM and op.mem.disp==0x488: memop=(i,op)
    base=ins.reg_name(memop[1].mem.base) if memop[1].mem.base else None
    if base in STACK: continue
    # dest = operand 0 for most
    is_w = (memop[0]==0 and ins.mnemonic not in ('cmp','test','lea','push')) or ins.mnemonic in ('and','or','xor','add','sub','inc','dec','not','neg','mov','movups','movaps','movq','movdqu','movdqa','btr','bts','btc')and memop[0]==0
    (writes if is_w else reads).append((a,by,mn,ops,fb,fe,base))
print("non-stack total",len(writes)+len(reads),"writes",len(writes),"reads/lea",len(reads))
fset=sorted(set(w[4] for w in writes),key=lambda x:int(x,16))
print("distinct writer functions",len(fset))
json.dump(writes,open("scratchpad/refute/writes.json","w"),indent=0)
