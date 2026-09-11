from advh import *
import collections
def build(E, maxspan=0x40000):
    seen={}; succ={}
    st=[E]
    while st:
        a=st.pop()
        if a in succ: continue
        g=list(md.disasm(DATA[a:a+16],a))
        if not g: succ[a]=[]; seen[a]=None; continue
        i=g[0]; seen[a]=i
        s=[]
        if i.mnemonic=='ret': s=[]
        elif i.mnemonic=='jmp':
            if i.operands[0].type==X86_OP_IMM: s=[i.operands[0].imm]
        elif i.group(CS_GRP_JUMP):
            s=[i.address+i.size]
            if i.operands[0].type==X86_OP_IMM: s.append(i.operands[0].imm)
        else: s=[i.address+i.size]
        s=[t for t in s if abs(t-E)<maxspan]
        succ[a]=s
        st.extend(s)
    return seen,succ
def fwd(succ,src):
    r=set(); st=[src]
    while st:
        a=st.pop()
        if a in r: continue
        r.add(a); st.extend(succ.get(a,[]))
    return r
def back(succ,tgt):
    pred=collections.defaultdict(list)
    for a,ss in succ.items():
        for t in ss: pred[t].append(a)
    r=set(); st=[tgt]
    while st:
        a=st.pop()
        if a in r: continue
        r.add(a); st.extend(pred[a])
    return r
