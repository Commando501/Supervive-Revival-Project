from h import *
from capstone.x86 import *
import collections
E=0x035E9EC0; CALL=0x035EB13A
seen={}
def decode(a):
    if a in seen: return seen[a]
    g=list(md.disasm(DATA[a:a+16],a))
    seen[a]=g[0] if g else None
    return seen[a]
succ={}
stack=[E]
while stack:
    a=stack.pop()
    if not isinstance(a,int): print("BAD",repr(a)); break
    if a in succ: continue
    i=decode(a)
    if i is None: succ[a]=[]; continue
    s=[]
    if i.mnemonic=='ret': pass
    elif i.mnemonic=='jmp':
        if i.operands[0].type==X86_OP_IMM: s=[i.operands[0].imm]
        else: s=[]
    elif i.group(CS_GRP_JUMP):
        s=[i.address+i.size]
        if i.operands[0].type==X86_OP_IMM: s.append(i.operands[0].imm)
    else:
        s=[i.address+i.size]
    succ[a]=s
    for t in s: stack.append(t)
# forward reachability helper
def reach(src, avoid=None):
    r=set(); st=[src]
    while st:
        a=st.pop()
        if a in r: continue
        r.add(a)
        if a==avoid: continue
        for t in succ.get(a,[]): st.append(t)
    return r
print("nodes:",len(succ))
for probe in (0x035EA494,0x035EB112,0x035EA3EE,0x035EB04D):
    print("  from 0x%08X reaches SNP call: %s"%(probe, CALL in reach(probe)))
# which nodes CANNOT reach the call = bail regions
canreach=set()
# reverse
pred=collections.defaultdict(list)
for a,ss in succ.items():
    for t in ss: pred[t].append(a)
st=[CALL]; 
while st:
    a=st.pop()
    if a in canreach: continue
    canreach.add(a)
    for p in pred[a]: st.append(p)
bail_edges=[]
for a,ss in succ.items():
    if a in canreach and len(ss)==2:
        for t in ss:
            if t not in canreach:
                bail_edges.append((a,t))
print("EDGES that leave the can-reach-SNP region (true bail edges):")
for a,t in sorted(bail_edges):
    i=seen[a]
    print("   0x%08X %-34s -> 0x%08X"%(a,i.mnemonic+" "+i.op_str,t))
# also unconditional jmps leaving
for a,ss in succ.items():
    if a in canreach and len(ss)==1 and ss[0] not in canreach and seen[a].mnemonic=='jmp':
        print("   [jmp] 0x%08X -> 0x%08X"%(a,ss[0]))
